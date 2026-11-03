"""OAuth/account regressions use signed local fixtures; never contact providers."""
import concurrent.futures
import io
import json
import logging
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import MagicMock, patch

import test_regressions as fixtures
import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm
import account_routes
import account_providers
import chatgpt_oauth as oauth
import muse_accounts
from account_store import AccountVault


class AccountFixture:
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='account-case-', dir=fixtures.TEMP.name)
        self.vault = AccountVault(self.directory.name)
        self.patches = [patch.object(module, 'vault', self.vault) for module in (oauth, account_routes, account_providers, muse_accounts)]
        for item in self.patches: item.start()
        oauth.metadata.cache_clear()
        self.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.jwk = json.loads(RSAAlgorithm.to_jwk(self.private_key.public_key()))
        self.jwk.update(kid='fixture', use='sig', alg='RS256')
        self.token_nonce = ''
        self.token_subject = 'fixture-subject'
        self.request_log = []
        self.transport = patch.object(oauth, 'request_first_party', side_effect=self.request)
        self.transport.start()

    def tearDown(self):
        self.transport.stop()
        oauth.metadata.cache_clear()
        for item in reversed(self.patches): item.stop()
        self.directory.cleanup()

    def encoded_identity(self, **changes):
        claims = {'sub': self.token_subject, 'iss': oauth.ISSUER, 'aud': 'oaiapp_fixture',
                  'iat': int(time.time()), 'exp': int(time.time()) + 600, 'nonce': self.token_nonce,
                  'email': 'fixture@example.invalid'}
        claims.update(changes)
        return jwt.encode(claims, self.private_key, algorithm='RS256', headers={'kid': 'fixture'})

    def request(self, method, url, **kwargs):
        self.request_log.append((method, url, kwargs))
        if url.endswith('/.well-known/openid-configuration'):
            return httpx.Response(200, json={'issuer': oauth.ISSUER, 'authorization_endpoint': oauth.AUTHORIZE,
                'token_endpoint': oauth.TOKEN, 'jwks_uri': oauth.ISSUER + '/.well-known/jwks.json',
                'revocation_endpoint': oauth.ISSUER + '/oauth/revoke'})
        if url.endswith('/jwks.json'): return httpx.Response(200, json={'keys': [self.jwk]})
        if url == oauth.TOKEN:
            data = kwargs['data']
            self.assertNotEqual(data['client_id'], 'dynamic_agent_client')
            if data['grant_type'] == 'refresh_token':
                time.sleep(.03)
                return httpx.Response(200, json={'access_token': 'rotated-fixture-access', 'refresh_token': 'rotated-fixture-refresh',
                                               'expires_in': 3600, 'token_type': 'Bearer'})
            return httpx.Response(200, json={'access_token': 'fixture-access-secret', 'refresh_token': 'fixture-refresh-secret',
                'id_token': self.encoded_identity(), 'expires_in': 3600, 'token_type': 'Bearer', 'scope': oauth.SCOPES})
        if url.endswith('/models'):
            return httpx.Response(200, json={'models': [{'slug': 'fixture-model', 'display_name': 'Fixture', 'visibility': 'list'}, {'slug': 'hidden', 'visibility': 'hidden'}]})
        if url.endswith('/oauth/revoke'): return httpx.Response(200)
        raise AssertionError('Unexpected first-party request')

    def connect(self):
        started = oauth.begin_chatgpt('http://127.0.0.1:8100/api/accounts/oauth/chatgpt/callback')
        self.token_nonce = parse_qs(urlsplit(started['authorizationUrl']).query)['nonce'][0]
        account = oauth.finish_chatgpt(started['attemptId'], code='fixture-code', client_id='oaiapp_fixture')
        return account, started


class OAuthTests(AccountFixture, unittest.TestCase):
    def test_disconnect_invalidates_pending_reauthorization(self):
        account, _ = self.connect()
        pending = oauth.begin_chatgpt('http://127.0.0.1:8100/api/accounts/oauth/chatgpt/callback', account['id'])
        params = parse_qs(urlsplit(pending['authorizationUrl']).query)
        self.assertIn('login_hint', params)
        self.assertNotIn('id_token_hint', params)
        oauth.disconnect_chatgpt(account['id'])
        with self.assertRaises(fixtures.main.HTTPException): oauth.finish_chatgpt(pending['attemptId'], code='late')
        record = self.vault.account(account['id'])
        self.assertEqual(record['status'], 'disconnected')
        self.assertNotIn('refresh_token', record)

    def test_disconnect_during_code_exchange_prevents_late_token_commit(self):
        account, _ = self.connect()
        pending = oauth.begin_chatgpt('http://127.0.0.1:8100/api/accounts/oauth/chatgpt/callback', account['id'])
        self.token_nonce = parse_qs(urlsplit(pending['authorizationUrl']).query)['nonce'][0]
        def disconnect_during_exchange(method, url, **kwargs):
            if url == oauth.TOKEN: oauth.disconnect_chatgpt(account['id'])
            return self.request(method, url, **kwargs)
        with patch.object(oauth, 'request_first_party', side_effect=disconnect_during_exchange):
            with self.assertRaises(fixtures.main.HTTPException): oauth.finish_chatgpt(pending['attemptId'], code='late')
        self.assertEqual(self.vault.account(account['id'])['status'], 'disconnected')
        self.assertNotIn('refresh_token', self.vault.account(account['id']))

    def test_muse_usage_is_allowlisted_and_unknown_is_not_zero(self):
        value = {'source':'muse-settings','session':'must-not-leak','rows':[
            {'kind':'weekly','label':'Free','description':'Resets Nov 6','valueLabel':'0% used','usedPercent':0,'access_token':'must-not-leak'}]}
        clean = muse_accounts.sanitize_usage(value)
        self.assertEqual(clean['rows'][0]['usedPercent'],0)
        self.assertNotIn('must-not-leak',json.dumps(clean))
        for invalid in [None,float('nan'),True,101,-1]:
            value['rows'][0]['usedPercent']=invalid
            with self.assertRaises(fixtures.main.HTTPException): muse_accounts.sanitize_usage(value)

    def test_muse_usage_commits_only_after_complete_and_returns_no_session(self):
        identifier='muse-usage-fixture'
        old={'source':'muse-settings','checkedAt':1,'rows':[]}
        state={'cookies':[{'domain':'muse.ai','name':'hatch_sess','value':'private-session'}],'origins':[]}
        with self.vault.transaction() as data:
            data['accounts'][identifier]={'id':identifier,'provider':'muse','status':'connected','canGenerate':True,'session':state,'usage':old}
        usage={'source':'muse-settings','rows':[{'kind':'additional','label':'Additional tokens','description':'Never expires','valueLabel':'1B remaining','usedPercent':0}]}
        def worker(complete):
            process=MagicMock(); process.stdin=io.StringIO(); process.poll.return_value=0; process.returncode=0
            events=[{'type':'usage','usage':usage},{'type':'session','session':state}]+([{'type':'complete'}] if complete else [])
            process.stdout=io.StringIO(''.join(json.dumps(e)+'\n' for e in events))
            return process
        with patch.object(muse_accounts.shutil,'which',return_value='node'),patch.object(muse_accounts.subprocess,'Popen',return_value=worker(False)):
            with self.assertRaises(fixtures.main.HTTPException): muse_accounts.refresh_muse_usage(identifier)
        self.assertEqual(self.vault.account(identifier)['usage'],old)
        with patch.object(muse_accounts.shutil,'which',return_value='node'),patch.object(muse_accounts.subprocess,'Popen',return_value=worker(True)):
            result=muse_accounts.refresh_muse_usage(identifier)
        self.assertEqual(result['usage']['rows'][0]['valueLabel'],'1B remaining')
        public=account_routes.accounts()['accounts'][0]
        self.assertIn('usage',public)
        self.assertNotIn('private-session',json.dumps(public))
        # A new verified login must not inherit another session's cached quota.
        with self.vault.transaction() as data: data['accounts'][identifier].update(status='pending')
        with patch.object(muse_accounts.shutil,'which',return_value='node'),patch.object(muse_accounts.subprocess,'Popen',return_value=worker(True)):
            list(muse_accounts.worker_events(identifier,'login'))
        self.assertNotIn('usage',self.vault.account(identifier))

    def test_registration_pkce_one_time_callback_and_encrypted_storage(self):
        account, started = self.connect()
        params = parse_qs(urlsplit(started['authorizationUrl']).query)
        self.assertEqual(params['client_id'], ['dynamic_agent_client'])
        self.assertEqual(params['code_challenge_method'], ['S256'])
        self.assertEqual(params['resource'], [oauth.RESOURCE])
        self.assertTrue(account['canGenerate'])
        self.assertNotIn('access_token', account)
        encrypted = (Path(self.directory.name) / 'accounts.enc').read_bytes()
        self.assertNotIn(b'fixture-access-secret', encrypted)
        self.assertNotIn(b'fixture@example.invalid', encrypted)
        self.assertEqual(oauth.attempt_status(started['attemptId'])['status'], 'connected')
        with self.assertRaises(fixtures.main.HTTPException): oauth.finish_chatgpt(started['attemptId'], code='replay', client_id='oaiapp_fixture')
        with self.assertRaises(fixtures.main.HTTPException): oauth.finish_chatgpt('unrelated-state', code='fixture')
        code_request = next(row[2]['data'] for row in self.request_log if row[1] == oauth.TOKEN)
        self.assertEqual(code_request['redirect_uri'], params['redirect_uri'][0])
        self.assertTrue(code_request['code_verifier'])

    def test_signature_nonce_issuer_audience_and_expiry_checked(self):
        self.token_nonce = 'expected-nonce'
        for changes in [{'nonce': 'wrong'}, {'iss': 'https://evil.invalid'}, {'aud': 'other-client'}, {'exp': int(time.time()) - 100}]:
            with self.subTest(changes=changes), self.assertRaises(fixtures.main.HTTPException):
                oauth.verify_identity(self.encoded_identity(**changes), 'oaiapp_fixture', 'expected-nonce')
        self.token_nonce = 'correct'
        self.assertEqual(oauth.verify_identity(self.encoded_identity(), 'oaiapp_fixture', 'correct')['sub'], self.token_subject)
        forged = jwt.encode({'sub': 'forged', 'exp': int(time.time())+600}, 'fixture-hmac-' + 'x'*32, algorithm='HS256', headers={'kid': 'fixture'})
        with self.assertRaises(fixtures.main.HTTPException): oauth.verify_identity(forged, 'oaiapp_fixture')

    def test_refresh_rotation_is_serialized_and_persists_atomically(self):
        account, _ = self.connect()
        with self.vault.transaction() as data: data['accounts'][account['id']]['expiresAt'] = time.time()-1
        self.request_log.clear()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: oauth.access_credentials(account['id']), range(2)))
        self.assertEqual(sum(row[1] == oauth.TOKEN for row in self.request_log), 1)
        self.assertTrue(all(r['access_token'] == 'rotated-fixture-access' for r in results))
        self.assertEqual(self.vault.account(account['id'])['refresh_token'], 'rotated-fixture-refresh')

    def test_reauthorization_rejects_different_identity_and_client(self):
        account, _ = self.connect()
        started = oauth.begin_chatgpt('http://127.0.0.1:8100/api/accounts/oauth/chatgpt/callback', account['id'])
        self.token_nonce = parse_qs(urlsplit(started['authorizationUrl']).query)['nonce'][0]
        self.token_subject = 'different-person'
        with self.assertRaises(fixtures.main.HTTPException): oauth.finish_chatgpt(started['attemptId'], code='fixture-code')
        self.assertEqual(self.vault.account(account['id'])['subject'], 'fixture-subject')
        started = oauth.begin_chatgpt('http://127.0.0.1:8100/api/accounts/oauth/chatgpt/callback', account['id'])
        with self.assertRaises(fixtures.main.HTTPException): oauth.finish_chatgpt(started['attemptId'], code='fixture-code', client_id='other-client')

    def test_grants_models_and_disconnect_do_not_expose_tokens(self):
        account, _ = self.connect()
        self.assertEqual(oauth.list_models(account['id']), [{'id':'fixture-model','name':'Fixture'}])
        with self.vault.transaction() as data: data['accounts'][account['id']]['canGenerate'] = False
        with self.assertRaises(fixtures.main.HTTPException): oauth.access_credentials(account['id'])
        result = oauth.disconnect_chatgpt(account['id'])
        self.assertTrue(result['revocationConfirmed'])
        saved = self.vault.account(account['id'])
        self.assertNotIn('access_token', saved)
        self.assertNotIn('refresh_token', saved)
        self.assertNotIn('id_token', saved)
        self.assertEqual(saved['client_id'], 'oaiapp_fixture')

    def test_callback_access_log_redacts_authorization_code(self):
        record = logging.LogRecord('uvicorn.access', logging.INFO, '', 1, '%s %s %s %s %s',
            ('127.0.0.1', 'GET', '/api/accounts/oauth/chatgpt/callback?code=private-code&state=private-state', '1.1', 200), None)
        account_routes.CallbackLogFilter().filter(record)
        self.assertNotIn('private-code', record.getMessage())
        self.assertNotIn('private-state', record.getMessage())

    def test_responses_adapter_requires_completed_and_filters_unsupported_fields(self):
        account, _ = self.connect()
        received = []
        def upstream(request):
            received.append(json.loads(request.content))
            body = 'data: '+json.dumps({'type':'response.output_text.delta','delta':'written'})+'\n\n'
            body += 'data: '+json.dumps({'type':'response.completed'})+'\n\n'
            return httpx.Response(200, text=body)
        client = httpx.Client(transport=httpx.MockTransport(upstream))
        with patch.object(account_providers, 'first_party_target', return_value=(httpx.URL('https://93.184.216.34/v1/responses'),'api.openai.com','api.openai.com')), patch.object(account_providers.httpx, 'Client', return_value=client):
            self.assertEqual(''.join(account_providers.chatgpt_text(account['id'], [{'role':'system','content':'write'}, {'role':'user','content':'novel'}], 'fixture-model')), 'written')
        self.assertEqual(received[0]['instructions'], 'write')
        self.assertFalse(received[0]['store']); self.assertTrue(received[0]['stream'])
        self.assertNotIn('temperature', received[0]); self.assertNotIn('max_output_tokens', received[0])
        self.assertTrue(all(row['role'] != 'system' for row in received[0]['input']))
        client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text='data: {"type":"response.output_text.delta","delta":"partial"}\n\n')))
        with patch.object(account_providers, 'first_party_target', return_value=(httpx.URL('https://93.184.216.34/v1/responses'),'api.openai.com','api.openai.com')), patch.object(account_providers.httpx, 'Client', return_value=client):
            with self.assertRaises(fixtures.main.HTTPException): list(account_providers.chatgpt_text(account['id'], [{'role':'user','content':'novel'}], 'fixture-model'))

    def test_muse_ipc_keeps_session_private_and_requires_completed_worker(self):
        identifier = 'fixture-muse'
        with self.vault.transaction() as data:
            data['accounts'][identifier] = {'id':identifier,'provider':'muse','label':'Muse','status':'pending','canGenerate':False}
        state = {'cookies':[{'domain':'muse.ai','name':'hatch_sess','value':'private-cookie'}],'origins':[]}
        with self.vault.transaction() as data: data['accounts'][identifier].update(status='connected', session=state)
        process = MagicMock()
        process.poll.return_value = 0; process.returncode = 0
        process.stdout = io.StringIO('\n'.join(json.dumps(e) for e in [
            {'type':'delta','text':'novel'}, {'type':'session','session':state}, {'type':'complete'}])+'\n')
        with patch.object(muse_accounts.shutil, 'which', return_value='node'), patch.object(muse_accounts.subprocess,'Popen',return_value=process) as launch:
            self.assertEqual(list(muse_accounts.worker_events(identifier,'generate',session=state,messages=[])), ['novel'])
        self.assertNotIn('private-cookie', str(launch.call_args.args))
        self.assertNotIn('session', self.vault.accounts()[0])
        self.assertNotIn(b'private-cookie', (Path(self.directory.name)/'accounts.enc').read_bytes())
        with self.vault.transaction() as data: data['accounts'][identifier].update(status='pending', canGenerate=False)
        process = MagicMock(); process.poll.return_value=0; process.returncode=1
        process.stdout = io.StringIO(json.dumps({'type':'session','session':state})+'\n')
        with patch.object(muse_accounts.shutil,'which',return_value='node'), patch.object(muse_accounts.subprocess,'Popen',return_value=process):
            with self.assertRaises(fixtures.main.HTTPException): list(muse_accounts.worker_events(identifier,'login'))
        self.assertEqual(self.vault.account(identifier)['status'], 'pending')

    def test_cancelled_or_superseded_muse_login_cannot_resurrect_session(self):
        identifier = 'cancelled-muse'
        with self.vault.transaction() as data:
            data['accounts'][identifier] = {'id':identifier,'provider':'muse','status':'pending','pendingAttempt':'old'}
        muse_accounts.disconnect_muse(identifier)
        with patch.object(muse_accounts.shutil,'which',return_value='node'), patch.object(muse_accounts.subprocess,'Popen') as launch:
            with self.assertRaises(fixtures.main.HTTPException): list(muse_accounts.worker_events(identifier,'login',attempt_id='old'))
            launch.assert_not_called()
        self.assertEqual(self.vault.account(identifier)['status'], 'disconnected')
        with self.vault.transaction() as data:
            data['accounts'][identifier].update(status='pending', pendingAttempt='new')
        with patch.object(muse_accounts.shutil,'which',return_value='node'), patch.object(muse_accounts.subprocess,'Popen') as launch:
            with self.assertRaises(fixtures.main.HTTPException): list(muse_accounts.worker_events(identifier,'login',attempt_id='old'))
            launch.assert_not_called()
        self.assertEqual(self.vault.account(identifier)['pendingAttempt'], 'new')


class AccountAPITests(AccountFixture, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=fixtures.main.app, client=('127.0.0.1',1234)), base_url='http://localhost:8100', headers=fixtures.AUTH)

    async def asyncTearDown(self): await self.client.aclose()

    async def test_accounts_require_app_auth_and_local_login_has_real_origin_check(self):
        self.assertEqual((await self.client.get('/api/accounts',headers={'Authorization':''})).status_code,401)
        response = await self.client.post('/api/accounts/chatgpt/login', json={})
        self.assertEqual(response.status_code,400)
        response = await self.client.post('/api/accounts/chatgpt/login', json={}, headers={'Origin':'http://localhost:5273'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(parse_qs(urlsplit(response.json()['authorizationUrl']).query)['client_id'],['dynamic_agent_client'])
        invalid = await self.client.get('/api/accounts/oauth/chatgpt/callback?state=invalid&code=never-display-this',headers={'Authorization':''})
        self.assertEqual(invalid.status_code,400)
        self.assertNotIn('never-display-this',invalid.text)

    async def test_account_reference_routes_without_forwarding_arbitrary_urls(self):
        with patch.object(fixtures.main,'complete_account_chat',return_value='novel') as complete, patch.object(fixtures.main,'provider_target') as target:
            response = await self.client.post('/api/proxy/chat',json={'url':'http://127.0.0.1/internal','headers':{'X-Novel-Account':'fixture-account'},'body':{'messages':[{'role':'user','content':'write'}],'model':'fixture-model'}})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['choices'][0]['message']['content'],'novel')
        complete.assert_called_once(); target.assert_not_called()

    async def test_account_stream_failure_is_not_reported_as_success(self):
        def failed(*args):
            yield 'partial'
            raise fixtures.main.HTTPException(429,'quota exceeded')
        with patch.object(account_providers,'account_text',failed):
            response=await self.client.post('/api/proxy/chat',json={'accountId':'fixture-account','body':{'model':'fixture-model','messages':[],'stream':True}})
        self.assertIn('partial',response.text)
        self.assertIn('quota exceeded',response.text)
        self.assertNotIn('[DONE]',response.text)
