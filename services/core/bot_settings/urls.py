from django.urls import path

from .views import BotMessagesView

urlpatterns = [
    path("mensajes-bot/", BotMessagesView.as_view(), name="bot-messages"),
]
