Python challenge
================

This is a Python challenge to create a chat app with a microservice
architecture.

* Version: 0.1.0

Getting started
---------------

* You must have installed Python 3 and RabbitMQ for this 
application to work. Make sure RabbitMQ service is up and running.

* Create a virtualenv for this project

```bash
virtualenv3 --no-site-packages challenge-env
```
    
* Clone project from https://github.com/rober710/jobsitychallenge

```bash
cd challenge-env
git clone https://github.com/rober710/jobsitychallenge challenge
```

* Activate the virtualenv and install the requirements listed on
requirements.txt
 
 ```bash
 cd challenge
 source bin/activate
 pip install -r requirements.txt
 ```

## Usage
This application consists of a bot that makes queries to the Yahoo
Finance Api and a Chat application in Django that serves as the
web frontend to post messages for users and commands for the bot.
The applications are decoupled and are connected between them using
a RabbitMQ queue.

1. Start the bot process in one shell with the following command:

```bash
python bot_main.py
```

2. In another shell, start the Django app with the following command:

```bash
python manage.py migrate
python manage.py runserver
```

3. Point your browser to http://127.0.0.1:8000 to see the login page
of the application. The sqlite database provided contains two
users: rober and andre. The password for these users is admin1234567.

4. Start posting messages. Messages are visible to all users.
You can also post commands to the bot to query financial information
from the Yahoo API. These two commands are implemented:

```
/stock=company_id
/day_range=company_id
```

For example:

```
/stock=AAPL
/day_range=AAPL
```
