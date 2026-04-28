from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('words/', views.word_list, name='word_list'),
    path('words/add/', views.add_word, name='add_word'),
    path('words/<int:pk>/edit/', views.edit_word, name='edit_word'),
    path('words/<int:pk>/delete/', views.delete_word, name='delete_word'),

    path('review/', views.review, name='review'),
    path('review/<int:pk>/rate/', views.rate_word, name='rate_word'),
    path('review/<int:pk>/data/', views.get_word_data, name='get_word_data'),

    path('ai/', views.ai_practice, name='ai_practice'),
    path('ai/check/', views.ai_check_sentence, name='ai_check_sentence'),
    path('ai/example/', views.ai_generate_example, name='ai_generate_example'),
    path('ai/synonyms/', views.ai_fetch_synonyms, name='ai_fetch_synonyms'),

    path('daily/', views.daily_practice, name='daily_practice'),
    path('daily/chat/', views.ai_chat_respond, name='ai_chat_respond'),
    path('daily/writing/', views.ai_evaluate_writing, name='ai_evaluate_writing'),
]
