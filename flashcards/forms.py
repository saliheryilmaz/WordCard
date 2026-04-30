from django import forms
from .models import Word


class WordForm(forms.ModelForm):
    class Meta:
        model = Word
        fields = ['english', 'turkish', 'synonyms', 'example_sentence', 'notes']
        widgets = {
            'english': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Bir kelime ekle..',
                'autocomplete': 'off',
                'id': 'id_english',
            }),
            'turkish': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Anlamanı buraya yaz..',
            }),
            'synonyms': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Eş Anlamını yaz..',
                'id': 'id_synonyms',
                'autocomplete': 'off',
            }),
            'example_sentence': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Örnek Cümleyi yaz..',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Kendi notlarin...',
            }),
        }
        labels = {
            'english': 'Ingilizce',
            'turkish': 'Turkce Anlami',
            'synonyms': 'Es Anlamlilar',
            'example_sentence': 'Ornek Cumle',
            'notes': 'Notlar',
        }
