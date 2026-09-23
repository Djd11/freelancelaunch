import json, urllib.request, urllib.error, secrets, hashlib, base64, time
def env(k):
    for line in open('.env'):
        if line.startswith(k+'='): return line.split('=',1)[1].strip().strip('"').strip("'")
base=env('SUPABASE_URL'); key=env('SUPABASE_ANON_KEY')
def b64url(raw): return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()
def probe(label, body):
    req=urllib.request.Request(base+"/auth/v1/otp", data=json.dumps(body).encode(),
      headers={"apikey":key,"Authorization":f"Bearer {key}","Content-Type":"application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req,timeout=25) as r:
            print(f"{label}: OK {r.status} body={r.read()[:150]!r}", flush=True)
    except urllib.error.HTTPError as e:
        print(f"{label}: HTTP {e.code} body={e.read().decode()[:400]!r}", flush=True)
v=b64url(secrets.token_bytes(32)); ch=b64url(hashlib.sha256(v.encode()).digest())
probe("with PKCE   ", {"email":f"a{int(time.time())}@example.com","code_challenge":ch,
   "code_challenge_method":"s256","options":{"email_redirect_to":"http://localhost:5000/auth/callback","data":{"display_name":"P"}}})
time.sleep(20)
probe("without PKCE", {"email":f"b{int(time.time())}@example.com",
   "options":{"email_redirect_to":"http://localhost:5000/auth/callback"}})
