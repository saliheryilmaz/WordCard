from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import math


class Word(models.Model):
    LEVEL_CHOICES = [
        ('new', 'Yeni'),
        ('learning', 'Öğreniliyor'),
        ('review', 'Tekrar'),
        ('mastered', 'Öğrenildi'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    english = models.CharField(max_length=200, verbose_name="İngilizce")
    turkish = models.CharField(max_length=200, verbose_name="Türkçe")
    example_sentence = models.TextField(blank=True, verbose_name="Örnek Cümle")
    synonyms = models.CharField(max_length=400, blank=True, verbose_name='Eş Anlamlılar',
                                help_text='Virgülle ayır: transient, fleeting, momentary')
    notes = models.TextField(blank=True, verbose_name="Notlar")

    # SM-2 Spaced Repetition fields
    repetitions = models.IntegerField(default=0)
    interval = models.IntegerField(default=1)          # gün cinsinden
    ease_factor = models.FloatField(default=2.5)
    next_review = models.DateTimeField(default=timezone.now)
    last_reviewed = models.DateTimeField(null=True, blank=True)

    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='new')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['next_review']

    def __str__(self):
        return f"{self.english} → {self.turkish}"

    @property
    def synonym_list(self):
        """'transient, fleeting' → ['transient', 'fleeting']"""
        if not self.synonyms:
            return []
        return [s.strip() for s in self.synonyms.split(',') if s.strip()]

    @property
    def is_due(self):
        return self.next_review <= timezone.now()

    def apply_rating(self, quality):
        """
        SM-2 algoritması.
        quality: 0=Hiç bilmedim, 1=Zor, 2=Orta, 3=Kolay, 4=Çok Kolay
        """
        # 0-5 arası skora çevir
        q_map = {0: 0, 1: 2, 2: 3, 3: 4, 4: 5}
        q = q_map.get(quality, 3)

        if q < 3:
            # Yanlış — başa dön
            self.repetitions = 0
            self.interval = 1
            self.level = 'learning'
        else:
            if self.repetitions == 0:
                self.interval = 1
            elif self.repetitions == 1:
                self.interval = 6
            else:
                self.interval = math.ceil(self.interval * self.ease_factor)
            self.repetitions += 1
            if self.interval >= 21:
                self.level = 'mastered'
            elif self.interval >= 7:
                self.level = 'review'
            else:
                self.level = 'learning'

        # Ease factor güncelle
        self.ease_factor += 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
        self.ease_factor = max(1.3, self.ease_factor)

        self.last_reviewed = timezone.now()
        self.next_review = timezone.now() + timezone.timedelta(days=self.interval)
        self.save()


class ReviewLog(models.Model):
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='logs')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    quality = models.IntegerField()
    reviewed_at = models.DateTimeField(auto_now_add=True)
    interval_after = models.IntegerField()

    class Meta:
        ordering = ['-reviewed_at']
