# encoding: utf-8

from django.conf.urls import include, url
from django.contrib.auth import views as auth_views

import chatroom.views as chatroom_views
import chatroom.restapi as rest_views

urlpatterns = [
    url(r'^$', chatroom_views.HomeView.as_view(), name='home'),
    url(r'^login$', auth_views.login, {'template_name': 'login.html'}, name='login'),
    url(r'^logout$', auth_views.logout, name='logout'),
    url(r'^chatroom$', chatroom_views.ChatroomView.as_view(), name='chat'),

    # API de mensajes para el chat
    url(r'^messages/post$', rest_views.PostMessage.as_view(), name='post'),
    url(r'^messages/list$', rest_views.GetLastMessages.as_view(), name='last-n'),
    url(r'^messages/updates$', rest_views.GetUpdates.as_view(), name='updates'),
    url(r'^misc/onlineusers$', rest_views.GetOnlineUsers.as_view(), name='onlineusers')
]
