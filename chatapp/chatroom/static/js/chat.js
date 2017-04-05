/* Chat page functions */

var Chat = {
    messageToSend: '',

    init: function() {
        this.cacheDOM();
        this.bindEvents();
        this.render();
    },

    cacheDOM: function() {
        this.$chatHistory = $('.chat-history');
        this.$button = $('button');
        this.$textarea = $('#message-to-send');
        this.$chatHistoryList = this.$chatHistory.find('ul');
        this.$extraMsg = $('#extra-msg');
        this.$userList = $('#user-list');
        this.myUserId = parseInt($('#user_id').val());
        this.messagesUrl = $('#messages_url').val();
        this.updatesUrl = $('#updates_url').val();
        this.onlineUrl = $('#online_url').val();
        this.lastTimestamp = null;
        this.updatesTimer = null;
        this.updateOnlineTimer = null;
    },

    bindEvents: function() {
        this.$button.on('click', this.sendMessage.bind(this));
        this.$textarea.on('keyup', this.sendMessageEnter.bind(this));
    },

    render: function() {
        var thisInstance = this;
        $.ajax({
            url: this.messagesUrl,
            type: 'GET',
            dataType: 'json'
        }).done(function(response) {
            if ($.isArray(response)) {
                for(var i = 0; i < response.length; i++) {
                    thisInstance.$chatHistoryList.append(thisInstance._createMessageMarkup(response[i]));
                    thisInstance.lastTimestamp = response[i].timestamp;
                }

                thisInstance.scrollToBottom();
                thisInstance.$textarea.val('');
            }
            // Activar el timer que consulta al servidor por mensajes nuevos.
            thisInstance.updatesTimer = setInterval($.proxy(thisInstance.getUpdates, thisInstance), 1000);
        }).fail(function(jqxhr) {
            if (jqxhr.responseJSON && jqxhr.responseJSON.message) {
                thisInstance.$extraMsg.text(jqxhr.responseJSON.message);
            }
            thisInstance.$textarea.val('');
        });

        this.getOnlineUsers();
        this.updateOnlineTimer = setInterval($.proxy(this.getOnlineUsers, this), 5000)
    },

    getUpdates: function() {
        var thisInstance = this;
        this.$extraMsg.empty();
        $.ajax({
            url: this.updatesUrl,
            type: 'GET',
            dataType: 'json',
            data: {
                last_t: this.lastTimestamp || ''
            }
        }).done(function(response) {
            if ($.isArray(response)) {
                for (var i = 0; i < response.length; i++) {
                    var message = response[i];
                    thisInstance.$chatHistoryList.append(thisInstance._createMessageMarkup(message));
                    thisInstance.scrollToBottom();
                    if (message.type == 'message') {
                        thisInstance.lastTimestamp = message.timestamp;
                    }
                }
            }
        }).fail(function(jqxhr) {
            if (jqxhr.responseJSON && jqxhr.responseJSON.message) {
                thisInstance.$extraMsg.text(jqxhr.responseJSON.message);
            } else {
                console && console.log(jqxhr.responseText);
            }
            thisInstance.$textarea.val('');
        });
    },

    renderMessage: function(messageInfo) {
        if (messageInfo.type == 'message') {
            var item = this._createMessageMarkup(messageInfo);
            this.$chatHistoryList.append(item);
            this.scrollToBottom();
            this.lastTimestamp = messageInfo.timestamp;
        }
        this.$textarea.val('');
    },

    getOnlineUsers: function() {
        var thisInstance = this;
        $.ajax({
            url: this.onlineUrl,
            type: 'GET',
            dataType: 'json'
        }).done(function(userList) {
            thisInstance.$userList.empty();
            if ($.isArray(userList)) {
                $.each(userList, function(index, userInfo) {
                    thisInstance.$userList.append(thisInstance._createOnlineUserEntry(userInfo));
                });
            }
        });
    },

    /**
     * Creates the DOM nodes for a message.
     * @param messageInfo Object with the information of the message to create.
     * @private
     */
    _createMessageMarkup: function(messageInfo) {
        // Was the message mine?
        var mine = this.myUserId === messageInfo.user.id;

        var item = $('<li/>');

        if (mine) {
            item.addClass('clearfix');
        }

        var header = $('<div/>').addClass('message-data');
        if (mine) {
            header.addClass('align-right');
            header.append($('<span/>').addClass('message-data-time').text(messageInfo.timestamp));
            header.append($('<span/>').addClass('message-data-name').text(messageInfo.user.username));
            header.append($('<i class="fa fa-circle me"></i>'));
        } else {
            header.append($('<span/>').addClass('message-data-name').append(
                $('<i class="fa fa-circle online"></i>')).text(messageInfo.user.username));
            header.append($('<span/>').addClass('message-data-time').text(messageInfo.timestamp));
        }

        header.appendTo(item);
        var content = $('<div/>').attr('class', 'message ' + (mine ? 'other-message float-right'
            : 'my-message'));
        content.text(messageInfo.text);
        content.appendTo(item);

        return item;
    },

    _createOnlineUserEntry: function(onlineUserInfo) {
        var item = $('<li/>').addClass('clearfix');
        item.append($('<img/>').attr({
            src: '/assets/img/user_avatar.png',
            alt: onlineUserInfo.name
        }));
        var about = $('<div/>').addClass('about');
        about.append($('<div/>').addClass('name').text(onlineUserInfo.name));
        about.append($('<div/>').addClass('status').append($('<i/>').addClass('fa fa-circle online'))
            .text('En línea'));

        about.appendTo(item);
        return item;
    },

    sendMessage: function() {
        var thisInstance = this;
        $.ajax({
            url: this.$textarea.attr('data-ajax-url'),
            type: 'POST',
            dataType: 'json',
            headers: {
                'X-CSRFToken': $.cookie('csrftoken')
            },
            data: {
                message: this.$textarea.val().trim()
            }
        }).done($.proxy(this.renderMessage, this)).fail(function(jqxhr) {
            if (jqxhr.responseJSON && jqxhr.responseJSON.message) {
                thisInstance.$extraMsg.text(jqxhr.responseJSON.message);
            }
        });
        thisInstance.$textarea.val('');
        this.$extraMsg.empty();
    },

    sendMessageEnter: function(event) {
        // enter was pressed
        if (event.keyCode === 13) {
            this.sendMessage();
        }
    },

    scrollToBottom: function() {
        this.$chatHistory.scrollTop(this.$chatHistory[0].scrollHeight);
    },

    getCurrentTime: function() {
        return new Date().toLocaleTimeString().replace(/([\d]+:[\d]{2})(:[\d]{2})(.*)/, "$1$3");
    },

    getRandomItem: function(arr) {
        return arr[Math.floor(Math.random() * arr.length)];
    }

};

$(function() {
    Chat.init();

    var searchFilter = {
        options: {valueNames: ['name']},
        init: function() {
            var userList = new List('people-list', this.options);
            var noItems = $('<li id="no-items-found">No items found</li>');

            userList.on('updated', function(list) {
                if (list.matchingItems.length === 0) {
                    $(list.list).append(noItems);
                } else {
                    noItems.detach();
                }
            });
        }
    };

    searchFilter.init();
});
