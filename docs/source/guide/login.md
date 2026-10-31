# Login

`wbi_login` provides the login functionality and also stores the cookies and edit tokens required (For security reasons,
every MediaWiki edit requires an edit token). There are multiple methods to login:

* `wbi_login.OAuth2(consumer_token, consumer_secret)` (recommended)
* `wbi_login.OAuth1(consumer_token, consumer_secret, access_token, access_secret)`
* `wbi_login.Clientlogin(user, password)`
* `wbi_login.Login(user, password)`

There is more parameters available. If you want to authenticate on another instance than Wikidata, you can set the
mediawiki_api_url, mediawiki_rest_url or mediawiki_index_url. Read the documentation for more information.

## Login using OAuth1 or OAuth2

OAuth is the authentication method recommended by the MediaWiki developers. It can be used to authenticate a bot or to
use WBI as a backend for an application.

### As a bot

If you want to use WBI with a bot account, you should use OAuth as
an [Owner-only consumer](https://www.mediawiki.org/wiki/OAuth/Owner-only_consumers). This allows to use the
authentication without the "continue oauth" step.

The first step is to request a new OAuth consumer on your MediaWiki instance on the page
"Special:OAuthConsumerRegistration", the "Owner-only" (or "This consumer is for use only by ...") has to be checked and
the correct version of the OAuth protocol must be set (OAuth 2.0). You will get a consumer token and consumer secret
(and an access token and access secret if you chose OAuth 1.0a). For a Wikimedia instance (like Wikidata), you need to
use the [Meta-Wiki website](https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration).

Example if you use OAuth 2.0:

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.OAuth2(consumer_token='<your_client_app_key>', consumer_secret='<your_client_app_secret>')
```

Example if you use OAuth 1.0a:

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.OAuth1(consumer_token='<your_consumer_key>', consumer_secret='<your_consumer_secret>',
                                  access_token='<your_access_token>', access_secret='<your_access_secret>')
```

### To impersonate a user (OAuth 1.0a)

If WBI is to be used as a backend for a web application, the script must use OAuth for authentication, WBI supports
this, you just need to specify consumer key and consumer secret when instantiating `wbi_login.OAuth1`. Unlike login by
username and password, OAuth is a 2-step process, as manual confirmation of the user for the OAuth login is required.
This means that the `wbi_login.OAuth1.continue_oauth()` method must be called after creating the `wbi_login.OAuth1`
instance.

Example:

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.OAuth1(consumer_token='<your_consumer_key>', consumer_secret='<your_consumer_secret>')
login_instance.continue_oauth(oauth_callback_data='<the_callback_url_returned>')
```

The `wbi_login.OAuth1.continue_oauth()` method will either ask the user for a callback URL (normal bot execution) or
take a parameter. Thus, in the case where WBI is used as a backend for a web application for example, the callback will
provide the authentication information directly to the backend and thus no copy and paste of the callback URL is needed.

## Login with a bot password

It's a good practice to use [Bot password](https://www.mediawiki.org/wiki/Manual:Bot_passwords) instead of simple
username and password, this allows limiting the permissions given to the bot.

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.Login(user='<bot user name>', password='<bot password>')
```

## Login with a username and a password

If you want to log in with your user account, you can use the "clientlogin" authentication method. This method is not
recommended.

```python
from wikibaseintegrator import wbi_login

login_instance = wbi_login.Clientlogin(user='<user name>', password='<password>')
```
