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
