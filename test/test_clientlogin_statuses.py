import pytest

from wikibaseintegrator import wbi_login
from wikibaseintegrator.wbi_login import LoginError


@pytest.fixture
def clientlogin_answers(wikibase, monkeypatch):
    """Make the clientlogin action of the test Wikibase answer with the given clientlogin result."""
    answers = []
    monkeypatch.setattr(wikibase, '_action_clientlogin', lambda params: {'clientlogin': answers.pop(0)})
    return answers


@pytest.mark.parametrize('result,message', [
    # The statuses of API:Clientlogin besides PASS and FAIL: REDIRECT has a redirect target and no message
    ({'status': 'REDIRECT', 'redirecttarget': 'https://idp.example.org/login'}, r'^Login failed \(REDIRECT\)\. .*https://idp\.example\.org/login'),
    ({'status': 'UI', 'message': 'Enter the verification code from your app.', 'messagecode': 'oathauth-auth-ui', 'requests': []},
     r"^Login failed \(oathauth-auth-ui\)\. Message: 'Enter the verification code from your app\.'$"),
    ({'status': 'RESTART', 'message': 'The login could not be completed.', 'messagecode': 'authmanager-authn-no-local-user'},
     r"^Login failed \(authmanager-authn-no-local-user\)\. Message: 'The login could not be completed\.'$"),
    ({'status': 'FAIL'}, r"^Login failed \(FAIL\)\."),
])
def test_status_other_than_pass(clientlogin_answers, result, message):
    clientlogin_answers.append(result)

    # A missing messagecode or message used to raise KeyError
    with pytest.raises(LoginError, match=message):
        wbi_login.Clientlogin(user='TestUser', password='password')
