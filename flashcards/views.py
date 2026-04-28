import os
import json
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Count, Q
from .models import Word, ReviewLog
from .forms import WordForm

from django.conf import settings
GROQ_API_KEY = getattr(settings, 'GROQ_API_KEY', os.environ.get('GROQ_API_KEY', ''))
GROQ_URL     = 'https://api.groq.com/openai/v1/chat/completions'
GROQ_MODEL   = 'llama-3.3-70b-versatile'

def call_groq(messages, max_tokens=600):
    headers = {
        'Authorization': f'Bearer {GROQ_API_KEY}',
        'Content-Type': 'application/json',
    }
    body = {
        'model': GROQ_MODEL,
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': 0.6,
    }
    resp = requests.post(GROQ_URL, headers=headers, json=body, timeout=15)
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content'].strip()


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Hesabın oluşturuldu! 🎉')
            return redirect('dashboard')
    else:
        form = UserCreationForm()
    return render(request, 'flashcards/auth.html', {'form': form, 'mode': 'register'})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'flashcards/auth.html', {'form': form, 'mode': 'login'})


def logout_view(request):
    logout(request)
    return redirect('login')


@login_required
def dashboard(request):
    words = Word.objects.filter(user=request.user)
    total = words.count()
    mastered_words = words.filter(level='mastered').order_by('-last_reviewed')
    not_mastered_words = words.exclude(level='mastered').order_by('-created_at')

    context = {
        'total': total,
        'mastered_count': mastered_words.count(),
        'not_mastered_count': not_mastered_words.count(),
        'mastered_words': mastered_words[:20],
        'not_mastered_words': not_mastered_words[:20],
    }
    return render(request, 'flashcards/dashboard.html', context)


@login_required
def word_list(request):
    query = request.GET.get('q', '')
    level_filter = request.GET.get('level', '')
    words = Word.objects.filter(user=request.user)
    if query:
        words = words.filter(
            Q(english__icontains=query) | Q(turkish__icontains=query)
        )
    if level_filter == 'mastered':
        words = words.filter(level='mastered')
    elif level_filter == 'not_mastered':
        words = words.exclude(level='mastered')
    elif level_filter:
        words = words.filter(level=level_filter)
    words = words.order_by('-created_at')
    return render(request, 'flashcards/word_list.html', {
        'words': words, 'query': query, 'level_filter': level_filter
    })


@login_required
def add_word(request):
    if request.method == 'POST':
        form = WordForm(request.POST)
        if form.is_valid():
            word = form.save(commit=False)
            word.user = request.user
            word.save()
            messages.success(request, f'"{word.english}" eklendi ✓')
            if request.POST.get('add_another'):
                return redirect('add_word')
            return redirect('word_list')
    else:
        form = WordForm()
    return render(request, 'flashcards/add_word.html', {'form': form})


@login_required
def edit_word(request, pk):
    word = get_object_or_404(Word, pk=pk, user=request.user)
    if request.method == 'POST':
        form = WordForm(request.POST, instance=word)
        if form.is_valid():
            form.save()
            messages.success(request, 'Kelime güncellendi ✓')
            return redirect('word_list')
    else:
        form = WordForm(instance=word)
    return render(request, 'flashcards/add_word.html', {'form': form, 'edit': True, 'word': word})


@login_required
def delete_word(request, pk):
    word = get_object_or_404(Word, pk=pk, user=request.user)
    if request.method == 'POST':
        word.delete()
        messages.success(request, 'Kelime silindi.')
    return redirect('word_list')


@login_required
def review(request):
    """Tekrar oturumu — mastered kelimeler 7 gunde bir gelir, digerleri her seferinde."""
    import random
    from datetime import timedelta

    now = timezone.now()
    week_ago = now - timedelta(days=7)

    # Mastered olmayanlar her zaman + mastered ama 7+ gun once gorulenler
    active_words = Word.objects.filter(user=request.user).exclude(level='mastered')
    due_mastered = Word.objects.filter(
        user=request.user, level='mastered'
    ).filter(
        Q(last_reviewed__isnull=True) | Q(last_reviewed__lte=week_ago)
    )

    all_words = (active_words | due_mastered).distinct()

    if not all_words.exists():
        # Hic kelime yok veya hepsi bu hafta goruldu
        total = Word.objects.filter(user=request.user).count()
        return render(request, 'flashcards/review_done.html', {'next_due': None, 'all_mastered': total > 0})

    queue = request.session.get('review_queue', None)

    if queue is None:
        ids = list(all_words.values_list('pk', flat=True))
        random.shuffle(ids)
        request.session['review_queue'] = ids
        request.session['review_wrong'] = []
        request.session['review_round'] = 1
        queue = ids

    if not queue:
        wrong = request.session.get('review_wrong', [])
        round_num = request.session.get('review_round', 1)

        if wrong and round_num == 1:
            random.shuffle(wrong)
            request.session['review_queue'] = wrong
            request.session['review_wrong'] = []
            request.session['review_round'] = 2
            queue = wrong
        else:
            request.session.pop('review_queue', None)
            request.session.pop('review_wrong', None)
            request.session.pop('review_round', None)
            return render(request, 'flashcards/review_done.html', {'next_due': None})

    word = get_object_or_404(Word, pk=queue[0], user=request.user)
    wrong_count = len(request.session.get('review_wrong', []))
    round_num = request.session.get('review_round', 1)

    return render(request, 'flashcards/review.html', {
        'word': word,
        'remaining': len(queue),
        'wrong_count': wrong_count,
        'round_num': round_num,
        'total': all_words.count(),
    })


@login_required
def rate_word(request, pk):
    """AJAX endpoint — biliyorum / bilmiyorum."""
    if request.method == 'POST':
        word = get_object_or_404(Word, pk=pk, user=request.user)
        data = json.loads(request.body)
        known = data.get('known', False)  # True = biliyorum, False = bilmiyorum

        # Kuyruğun başından bu kelimeyi çıkar
        queue = request.session.get('review_queue', [])
        if queue and queue[0] == pk:
            queue = queue[1:]

        wrong = request.session.get('review_wrong', [])

        if not known:
            # Bilmiyorum — SM-2 düşük puan, seviyeyi learning yap
            if pk not in wrong:
                wrong.append(pk)
            word.apply_rating(0)
            ReviewLog.objects.create(word=word, user=request.user, quality=0, interval_after=word.interval)
        else:
            # Biliyorum — mastered olarak işaretle
            word.level = 'mastered'
            word.last_reviewed = timezone.now()
            word.save()
            ReviewLog.objects.create(word=word, user=request.user, quality=4, interval_after=word.interval)

        request.session['review_queue'] = queue
        request.session['review_wrong'] = wrong
        request.session.modified = True

        next_word_id = queue[0] if queue else None

        return JsonResponse({
            'success': True,
            'next_word_id': next_word_id,
            'remaining': len(queue),
            'wrong_count': len(wrong),
        })

    return JsonResponse({'success': False})


@login_required
def get_word_data(request, pk):
    """Review sayfası için kelime verisi."""
    word = get_object_or_404(Word, pk=pk, user=request.user)
    return JsonResponse({
        'id': word.pk,
        'english': word.english,
        'turkish': word.turkish,
        'example_sentence': word.example_sentence,
        'notes': word.notes,
        'level': word.level,
        'interval': word.interval,
        'repetitions': word.repetitions,
        'synonyms': word.synonym_list,
    })


@login_required
def ai_practice(request):
    words = Word.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'flashcards/ai_practice.html', {'words': words})


@login_required
def ai_check_sentence(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if not GROQ_API_KEY:
        return JsonResponse({'error': 'GROQ_API_KEY ayarlanmamış.'}, status=500)

    data = json.loads(request.body)
    word     = data.get('word', '').strip()
    sentence = data.get('sentence', '').strip()
    if not word or not sentence:
        return JsonResponse({'error': 'Kelime ve cümle gerekli.'}, status=400)

    system_prompt = """You are an English language tutor helping a Turkish speaker prepare to move to Australia.
Your task: Check their sentence and give feedback in Turkish.
Respond ONLY in this exact JSON format (no markdown, no extra text):
{
  "score": <1-10 integer>,
  "is_correct": <true or false>,
  "grammar_feedback": "<Turkish: grammar issues or 'Gramer açısından mükemmel!'>",
  "naturalness_feedback": "<Turkish: does it sound natural to a native speaker?>",
  "better_version": "<improved English sentence or same if already great>",
  "explanation": "<Turkish: short explanation of why your version is better, or encouragement>",
  "extra_tip": "<Turkish: one small tip about this word's usage, collocations, or Australian English context>"
}"""

    try:
        raw = call_groq([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': f'Word: "{word}"\nStudent sentence: "{sentence}"'},
        ])
        result = json.loads(raw)

        if data.get('save_to_word') and result.get('is_correct'):
            try:
                word_obj = Word.objects.get(english__iexact=word, user=request.user)
                if not word_obj.example_sentence:
                    word_obj.example_sentence = sentence
                    word_obj.save()
            except Word.DoesNotExist:
                pass

        return JsonResponse({'success': True, 'result': result})

    except json.JSONDecodeError:
        cleaned = raw.replace('```json', '').replace('```', '').strip()
        try:
            return JsonResponse({'success': True, 'result': json.loads(cleaned)})
        except Exception:
            return JsonResponse({'error': 'AI yanıtı parse edilemedi.', 'raw': raw}, status=500)
    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'Groq zaman aşımı. Tekrar dene.'}, status=504)
    except requests.exceptions.HTTPError as e:
        return JsonResponse({'error': f'Groq API hatası: {str(e)}'}, status=502)


@login_required
def ai_fetch_synonyms(request):
    """AJAX — Groq ile otomatik es anlamli uret."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if not GROQ_API_KEY:
        return JsonResponse({'error': 'GROQ_API_KEY ayarlanmamis.'}, status=500)

    data = json.loads(request.body)
    word = data.get('word', '').strip()
    if not word:
        return JsonResponse({'error': 'Kelime gerekli.'}, status=400)

    prompt = f"""For the English word "{word}", give me:
1. 4-6 synonyms (similar meaning words)
2. 2-3 antonyms (opposite meaning words)
3. The most common register (formal/informal/neutral)
Respond ONLY in this exact JSON format, no markdown:
{{"synonyms": ["word1", "word2", "word3", "word4"],
"antonyms": ["word1", "word2"],
"register": "formal|informal|neutral",
"tip": "One short sentence in Turkish about when to use this word vs its synonyms"}}"""

    try:
        raw = call_groq([{'role': 'user', 'content': prompt}], max_tokens=300)
        cleaned = raw.replace('```json', '').replace('```', '').strip()
        result = json.loads(cleaned)
        return JsonResponse({'success': True, 'result': result})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def ai_generate_example(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if not GROQ_API_KEY:
        return JsonResponse({'error': 'GROQ_API_KEY ayarlanmamış.'}, status=500)

    data    = json.loads(request.body)
    word    = data.get('word', '').strip()
    turkish = data.get('turkish', '').strip()
    if not word:
        return JsonResponse({'error': 'Kelime gerekli.'}, status=400)

    prompt = f"""Generate 3 natural, varied example sentences for the English word "{word}" (Turkish meaning: {turkish}).
Respond ONLY in this JSON format:
{{"sentences": [{{"sentence": "...", "difficulty": "easy|medium|hard", "context": "Turkish: kısa bağlam açıklaması"}}]}}"""

    try:
        raw     = call_groq([{'role': 'user', 'content': prompt}], max_tokens=400)
        cleaned = raw.replace('```json', '').replace('```', '').strip()
        return JsonResponse({'success': True, 'result': json.loads(cleaned)})
    except requests.exceptions.HTTPError as e:
        return JsonResponse({'error': f'Groq API hatası: {e.response.status_code} — {e.response.text}'}, status=502)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── DAILY PRACTICE ──────────────────────────────────────────────────────────

DAILY_TOPICS = [
    {"en": "Describe your dream travel destination and why you want to go there.", "tr": "Hayalindeki seyahat destinasyonu"},
    {"en": "Talk about a movie or TV show that changed your perspective on life.", "tr": "Hayatına bakışını değiştiren bir film/dizi"},
    {"en": "What are the advantages and disadvantages of social media?", "tr": "Sosyal medyanın artıları ve eksileri"},
    {"en": "Describe a challenge you overcame and what you learned from it.", "tr": "Üstesinden geldiğin bir zorluk"},
    {"en": "If you could live in any era in history, which would you choose and why?", "tr": "Hangi tarihi dönemde yaşamak isterdin"},
    {"en": "What does your ideal day look like from morning to night?", "tr": "İdeal bir günün nasıl geçer"},
    {"en": "Talk about a book that influenced you and what made it special.", "tr": "Seni etkileyen bir kitap"},
    {"en": "What technology do you think will change the world in the next 10 years?", "tr": "Dünyayı değiştirecek teknoloji"},
    {"en": "Describe your favourite food and how it is prepared.", "tr": "En sevdiğin yemek ve yapılışı"},
    {"en": "What are the pros and cons of living in a big city vs. a small town?", "tr": "Büyük şehir mi, küçük kasaba mı"},
    {"en": "Talk about someone who has been a mentor or role model in your life.", "tr": "Hayatındaki bir mentor/rol model"},
    {"en": "If you could have any superpower, what would it be and how would you use it?", "tr": "Süper güç olsaydı"},
    {"en": "Describe a tradition or celebration that is important to you or your culture.", "tr": "Önemli bir gelenek ya da kutlama"},
    {"en": "What habits do you think are essential for a healthy and happy life?", "tr": "Sağlıklı ve mutlu bir yaşam için alışkanlıklar"},
    {"en": "Talk about your favourite hobby and how it started.", "tr": "En sevdiğin hobi ve nasıl başladı"},
    {"en": "If you could meet any historical figure, who would it be and what would you ask?", "tr": "Hangi tarihi kişiyle tanışmak isterdin"},
    {"en": "What do you think is the most important quality in a true friend?", "tr": "Gerçek bir arkadaşın en önemli özelliği"},
    {"en": "Talk about a skill you would love to master and why.", "tr": "Ustalaşmak istediğin bir beceri"},
    {"en": "Describe the place where you grew up and how it shaped who you are.", "tr": "Büyüdüğün yer ve seni nasıl şekillendirdi"},
    {"en": "What are your thoughts on climate change and what can individuals do about it?", "tr": "İklim değişikliği ve bireysel çözümler"},
    {"en": "Talk about your career goals and the steps you are taking to achieve them.", "tr": "Kariyer hedeflerin ve attığın adımlar"},
    {"en": "If you won the lottery, how would you spend the money?", "tr": "Piyangoda büyük ikramiye kazansaydın"},
    {"en": "What do you think makes a great leader? Give an example.", "tr": "Büyük bir lideri ne yapar"},
    {"en": "Describe a moment when you felt truly proud of yourself.", "tr": "Kendinden gerçekten gurur duyduğun an"},
    {"en": "Talk about the impact of artificial intelligence on everyday life.", "tr": "Yapay zekanın günlük hayata etkisi"},
    {"en": "What is your favourite season and what do you like to do during that time?", "tr": "En sevdiğin mevsim ve aktiviteler"},
    {"en": "If you could learn any language instantly, which would you choose and why?", "tr": "Anında öğrenebileceğin bir dil olsaydı"},
    {"en": "Talk about a time you had to make a difficult decision.", "tr": "Zor bir karar vermek zorunda kaldığın an"},
    {"en": "What are the most important things you have learned from your parents?", "tr": "Ebeveynlerinden öğrendiğin en önemli şeyler"},
    {"en": "Describe your perfect home — where it would be and what it would look like.", "tr": "Hayalindeki ev"},
    {"en": "What role does music play in your life?", "tr": "Müziğin hayatındaki yeri"},
    {"en": "Talk about a time you helped someone and how it made you feel.", "tr": "Birine yardım ettiğin ve nasıl hissettirdiği"},
    {"en": "If you could change one thing about the world, what would it be?", "tr": "Dünyada bir şeyi değiştirebilseydin"},
    {"en": "Describe a goal you are currently working towards.", "tr": "Şu an üzerinde çalıştığın bir hedef"},
    {"en": "What does success mean to you personally?", "tr": "Başarı senin için ne anlama gelir"},
    {"en": "Talk about a sport or physical activity you enjoy.", "tr": "Keyif aldığın bir spor veya fiziksel aktivite"},
    {"en": "If you could redesign your country's education system, what would you change?", "tr": "Eğitim sistemini yeniden tasarlasaydın"},
    {"en": "Describe a place you have visited that left a strong impression on you.", "tr": "Seni derinden etkileyen bir yer"},
    {"en": "What are the benefits and risks of working from home?", "tr": "Evden çalışmanın avantaj ve dezavantajları"},
    {"en": "Talk about how technology has changed the way people communicate.", "tr": "Teknoloji iletişimi nasıl değiştirdi"},
]


@login_required
def daily_practice(request):
    from datetime import date
    today = date.today()
    topic_index = (today.year * 366 + today.timetuple().tm_yday) % len(DAILY_TOPICS)
    topic = DAILY_TOPICS[topic_index]
    # Reset chat history when visiting the page fresh (GET)
    if request.method == 'GET':
        request.session['daily_chat_history'] = []
    return render(request, 'flashcards/daily_practice.html', {'topic': topic, 'all_topics': DAILY_TOPICS})


@login_required
def ai_chat_respond(request):
    """AJAX — AI speaking partner responds to user message and corrects if needed."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if not GROQ_API_KEY:
        return JsonResponse({'error': 'GROQ_API_KEY ayarlanmamış.'}, status=500)

    data = json.loads(request.body)
    user_message = data.get('message', '').strip()
    topic_en = data.get('topic', '').strip()

    if not user_message:
        return JsonResponse({'error': 'Mesaj boş olamaz.'}, status=400)

    # Build / retrieve session history (keep last 10 turns to manage token budget)
    history = request.session.get('daily_chat_history', [])

    system_prompt = f"""You are a friendly, encouraging English conversation partner for a Turkish speaker who wants to improve their English.
The topic of today's conversation is: "{topic_en}"

Rules:
1. Reply naturally and engagingly in English, as a real conversation partner would.
2. Keep your replies concise (2-4 sentences max) to encourage back-and-forth.
3. If the user makes a clear grammar mistake, gently correct it at the END of your reply in this exact format:
   💡 *Correction: "[their mistake]" → "[correct form]" — [brief Turkish explanation]*
4. If there is no mistake, do NOT add any correction note.
5. Ask a follow-up question to keep the conversation going.
6. Never switch to Turkish in your main response — only in the correction note."""

    messages_payload = [{'role': 'system', 'content': system_prompt}]
    # Append existing history
    for turn in history[-10:]:
        messages_payload.append({'role': turn['role'], 'content': turn['content']})
    messages_payload.append({'role': 'user', 'content': user_message})

    try:
        reply = call_groq(messages_payload, max_tokens=250)

        # Save to session history
        history.append({'role': 'user', 'content': user_message})
        history.append({'role': 'assistant', 'content': reply})
        request.session['daily_chat_history'] = history[-20:]  # keep last 20 entries
        request.session.modified = True

        return JsonResponse({'success': True, 'reply': reply})
    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'Groq zaman aşımı. Tekrar dene.'}, status=504)
    except requests.exceptions.HTTPError as e:
        return JsonResponse({'error': f'Groq API hatası: {str(e)}'}, status=502)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def ai_evaluate_writing(request):
    """AJAX — Evaluate a paragraph submitted by the user for the daily writing exercise."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if not GROQ_API_KEY:
        return JsonResponse({'error': 'GROQ_API_KEY ayarlanmamış.'}, status=500)

    data = json.loads(request.body)
    text = data.get('text', '').strip()
    topic_en = data.get('topic', '').strip()

    if len(text) < 20:
        return JsonResponse({'error': 'Lütfen daha uzun bir metin yaz (en az 20 karakter).'}, status=400)

    system_prompt = """You are a professional English writing coach for a Turkish speaker.
Evaluate the submitted paragraph and respond ONLY in this exact JSON format (no markdown, no extra text):
{
  "overall_score": <integer 1-10>,
  "grammar_score": <integer 1-10>,
  "vocabulary_score": <integer 1-10>,
  "fluency_score": <integer 1-10>,
  "summary": "<Turkish: 2-3 sentence overall summary of the writing>",
  "strengths": ["<Turkish: strength 1>", "<Turkish: strength 2>"],
  "improvements": [
    {"original": "<exact phrase from user's text>", "corrected": "<corrected version>", "explanation": "<Turkish: why>"}
  ],
  "better_version": "<A polished English rewrite of the entire paragraph, keeping the user's ideas>",
  "vocabulary_suggestions": [
    {"word": "<word they used>", "alternatives": ["<better word 1>", "<better word 2>"], "tip": "<Turkish: usage tip>"}
  ],
  "encouragement": "<Turkish: motivating closing message>"
}"""

    try:
        raw = call_groq([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': f'Topic: "{topic_en}"\n\nStudent paragraph:\n{text}'},
        ], max_tokens=800)
        cleaned = raw.replace('```json', '').replace('```', '').strip()
        result = json.loads(cleaned)
        return JsonResponse({'success': True, 'result': result})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'AI yanıtı parse edilemedi.', 'raw': raw}, status=500)
    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'Groq zaman aşımı. Tekrar dene.'}, status=504)
    except requests.exceptions.HTTPError as e:
        return JsonResponse({'error': f'Groq API hatası: {str(e)}'}, status=502)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ── DAILY PRACTICE ──────────────────────────────────────────────────────────

DAILY_TOPICS = [
    {"en": "Describe your dream travel destination and why you want to go there.", "tr": "Hayalindeki seyahat destinasyonu"},
    {"en": "Talk about a movie or TV show that changed your perspective on life.", "tr": "Hayatina bakisini degistiren bir film/dizi"},
    {"en": "What are the advantages and disadvantages of social media?", "tr": "Sosyal medyanin artilari ve eksileri"},
    {"en": "Describe a challenge you overcame and what you learned from it.", "tr": "Ustesinden geldigin bir zorluk"},
    {"en": "If you could live in any era in history, which would you choose and why?", "tr": "Hangi tarihi donemde yasamak isterdin"},
    {"en": "What does your ideal day look like from morning to night?", "tr": "Ideal bir gunun nasil gecer"},
    {"en": "Talk about a book that influenced you and what made it special.", "tr": "Seni etkileyen bir kitap"},
    {"en": "What technology do you think will change the world in the next 10 years?", "tr": "Dunyayi degistirecek teknoloji"},
    {"en": "Describe your favourite food and how it is prepared.", "tr": "En sevdigin yemek ve yapilisi"},
    {"en": "What are the pros and cons of living in a big city vs. a small town?", "tr": "Buyuk sehir mi, kucuk kasaba mi"},
    {"en": "Talk about someone who has been a mentor or role model in your life.", "tr": "Hayatindaki bir mentor/rol model"},
    {"en": "If you could have any superpower, what would it be and how would you use it?", "tr": "Super guc olsaydi"},
    {"en": "Describe a tradition or celebration that is important to you or your culture.", "tr": "Onemli bir gelenek ya da kutlama"},
    {"en": "What habits do you think are essential for a healthy and happy life?", "tr": "Saglikli ve mutlu bir yasam icin aliskanliklar"},
    {"en": "Talk about your favourite hobby and how it started.", "tr": "En sevdigin hobi ve nasil basladi"},
    {"en": "If you could meet any historical figure, who would it be and what would you ask?", "tr": "Hangi tarihi kisiyle tanisamak isterdin"},
    {"en": "What do you think is the most important quality in a true friend?", "tr": "Gercek bir arkadasin en onemli ozelligi"},
    {"en": "Talk about a skill you would love to master and why.", "tr": "Ustalasmak istedigin bir beceri"},
    {"en": "Describe the place where you grew up and how it shaped who you are.", "tr": "Buyudugum yer ve seni nasil sekillendirdi"},
    {"en": "What are your thoughts on climate change and what can individuals do about it?", "tr": "Iklim degisikligi ve bireysel cozumler"},
    {"en": "Talk about your career goals and the steps you are taking to achieve them.", "tr": "Kariyer hedeflerin ve attigin adimlar"},
    {"en": "If you won the lottery, how would you spend the money?", "tr": "Piyangoda buyuk ikramiye kazansaydin"},
    {"en": "What do you think makes a great leader? Give an example.", "tr": "Buyuk bir lideri ne yapar"},
    {"en": "Describe a moment when you felt truly proud of yourself.", "tr": "Kendinden gercekten gurur duydugum an"},
    {"en": "Talk about the impact of artificial intelligence on everyday life.", "tr": "Yapay zekanin gunluk hayata etkisi"},
    {"en": "What is your favourite season and what do you like to do during that time?", "tr": "En sevdigin mevsim ve aktiviteler"},
    {"en": "If you could learn any language instantly, which would you choose and why?", "tr": "Aninda ogrenebilecegin bir dil olsaydi"},
    {"en": "Talk about a time you had to make a difficult decision.", "tr": "Zor bir karar vermek zorunda kaldigin an"},
    {"en": "What are the most important things you have learned from your parents?", "tr": "Ebeveynlerinden ogrendigin en onemli seyler"},
    {"en": "Describe your perfect home — where it would be and what it would look like.", "tr": "Hayalindeki ev"},
    {"en": "What role does music play in your life?", "tr": "Muzigin hayatindaki yeri"},
    {"en": "Talk about a time you helped someone and how it made you feel.", "tr": "Birine yardim ettigin ve nasil hissettirdigi"},
    {"en": "If you could change one thing about the world, what would it be?", "tr": "Dunyada bir seyi degistirebilseydin"},
    {"en": "Describe a goal you are currently working towards.", "tr": "Su an uzerinde calistigin bir hedef"},
    {"en": "What does success mean to you personally?", "tr": "Basari senin icin ne anlama gelir"},
    {"en": "Talk about a sport or physical activity you enjoy.", "tr": "Keyif aldigin bir spor veya fiziksel aktivite"},
    {"en": "If you could redesign your country's education system, what would you change?", "tr": "Egitim sistemini yeniden tasarlasaydin"},
    {"en": "Describe a place you have visited that left a strong impression on you.", "tr": "Seni derinden etkileyen bir yer"},
    {"en": "What are the benefits and risks of working from home?", "tr": "Evden calismanin avantaj ve dezavantajlari"},
    {"en": "Talk about how technology has changed the way people communicate.", "tr": "Teknoloji iletisimi nasil degistirdi"},
]


@login_required
def daily_practice(request):
    from datetime import date
    today = date.today()
    topic_index = (today.year * 366 + today.timetuple().tm_yday) % len(DAILY_TOPICS)
    topic = DAILY_TOPICS[topic_index]
    if request.method == 'GET':
        request.session['daily_chat_history'] = []
    return render(request, 'flashcards/daily_practice.html', {'topic': topic, 'all_topics': DAILY_TOPICS})


@login_required
def ai_chat_respond(request):
    """AJAX — AI speaking partner, corrects mistakes inline."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if not GROQ_API_KEY:
        return JsonResponse({'error': 'GROQ_API_KEY ayarlanmamis.'}, status=500)

    data = json.loads(request.body)
    user_message = data.get('message', '').strip()
    topic_en     = data.get('topic', '').strip()
    if not user_message:
        return JsonResponse({'error': 'Mesaj bos olamaz.'}, status=400)

    history = request.session.get('daily_chat_history', [])

    system_prompt = f"""You are a friendly, encouraging English conversation partner for a Turkish speaker preparing to move to Australia.
Today's conversation topic: "{topic_en}"

Rules:
1. Reply naturally in English as a real conversation partner (2-4 sentences max).
2. If the user makes a clear grammar mistake, add a correction at the END in this exact format:
   CORRECTION: "[their mistake]" -> "[correct form]" | [brief Turkish explanation]
3. If no mistake, do NOT add any correction line.
4. Always end with a follow-up question to keep the conversation going.
5. Never switch to Turkish in your main reply."""

    payload = [{'role': 'system', 'content': system_prompt}]
    for turn in history[-10:]:
        payload.append({'role': turn['role'], 'content': turn['content']})
    payload.append({'role': 'user', 'content': user_message})

    try:
        reply = call_groq(payload, max_tokens=250)
        history.append({'role': 'user',      'content': user_message})
        history.append({'role': 'assistant', 'content': reply})
        request.session['daily_chat_history'] = history[-20:]
        request.session.modified = True
        return JsonResponse({'success': True, 'reply': reply})
    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'Groq zaman asimi. Tekrar dene.'}, status=504)
    except requests.exceptions.HTTPError as e:
        return JsonResponse({'error': f'Groq API hatasi: {str(e)}'}, status=502)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def ai_evaluate_writing(request):
    """AJAX — Evaluate daily writing paragraph."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if not GROQ_API_KEY:
        return JsonResponse({'error': 'GROQ_API_KEY ayarlanmamis.'}, status=500)

    data     = json.loads(request.body)
    text     = data.get('text', '').strip()
    topic_en = data.get('topic', '').strip()
    if len(text) < 20:
        return JsonResponse({'error': 'Lutfen daha uzun bir metin yaz (en az 20 karakter).'}, status=400)

    system_prompt = """You are a professional English writing coach for a Turkish speaker.
Evaluate the paragraph and respond ONLY in this exact JSON format (no markdown):
{
  "overall_score": <1-10>,
  "grammar_score": <1-10>,
  "vocabulary_score": <1-10>,
  "fluency_score": <1-10>,
  "summary": "<Turkish: 2-3 sentence overall summary>",
  "strengths": ["<Turkish strength 1>", "<Turkish strength 2>"],
  "improvements": [
    {"original": "<exact phrase>", "corrected": "<corrected>", "explanation": "<Turkish why>"}
  ],
  "better_version": "<polished English rewrite keeping user's ideas>",
  "vocabulary_suggestions": [
    {"word": "<word used>", "alternatives": ["<better 1>", "<better 2>"], "tip": "<Turkish tip>"}
  ],
  "encouragement": "<Turkish: motivating closing message>"
}"""

    try:
        raw     = call_groq([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user',   'content': f'Topic: "{topic_en}"\n\nStudent paragraph:\n{text}'},
        ], max_tokens=900)
        cleaned = raw.replace('```json', '').replace('```', '').strip()
        result  = json.loads(cleaned)
        return JsonResponse({'success': True, 'result': result})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'AI yaniti parse edilemedi.', 'raw': raw}, status=500)
    except requests.exceptions.Timeout:
        return JsonResponse({'error': 'Groq zaman asimi. Tekrar dene.'}, status=504)
    except requests.exceptions.HTTPError as e:
        return JsonResponse({'error': f'Groq API hatasi: {str(e)}'}, status=502)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
