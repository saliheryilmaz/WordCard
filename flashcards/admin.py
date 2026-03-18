from django.contrib import admin
from .models import Word, ReviewLog


@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ['english', 'turkish', 'level', 'interval', 'next_review', 'user']
    list_filter = ['level', 'user']
    search_fields = ['english', 'turkish']
    readonly_fields = ['repetitions', 'interval', 'ease_factor', 'next_review', 'last_reviewed']


@admin.register(ReviewLog)
class ReviewLogAdmin(admin.ModelAdmin):
    list_display = ['word', 'quality', 'interval_after', 'reviewed_at', 'user']
    list_filter = ['quality', 'user']
