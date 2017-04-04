# encoding: utf-8

from django.conf.urls import url

import chatroom.views as chatroom_views
import chatroom.restapi as rest_views

urlpatterns = [
    url(r'^$', chatroom_views.LoginView.as_view(), name='login'),
    url(r'^logout$', chatroom_views.LogoutView.as_view(), name='logout'),
    url(r'^chatroom$', chatroom_views.ChatroomView.as_view(), name='chat'),

    # API de mensajes para el chat
    url(r'^messages/post$', rest_views.PostMessage.as_view(), name='post'),
    url(r'^messages/list$', rest_views.GetLastMessages.as_view(), name='last-n'),
    url(r'^messages/updates$', rest_views.GetUpdates.as_view(), name='updates'),
    url(r'^misc/onlineusers$', rest_views.GetOnlineUsers.as_view(), name='onlineusers')
]
