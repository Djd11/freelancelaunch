"""Spike T1 — part A: OFFLINE introspection of the installed supabase-auth.

No network, no side effects. Answers:
  A1. exact import path of the storage protocol + its method names
  A2. whether the protocol is an ABC or a Protocol (subclassing contract)
  A3. EmailOtpType accepted literals (is "email" valid? is "sms"?)
  A4. sign_in_with_otp / verify_otp / sign_in_with_oauth /
      exchange_code_for_session signatures
  A5. what keys a storage backend actually receives in a PKCE flow
Run: .venv/bin/python docs/superpowers/spikes/spike_static.py
"""
import inspect
import sys

import supabase_auth
from supabase_auth import SyncGoTrueClient, SyncSupportedStorage

print(f"python={sys.version.split()[0]}  supabase_auth={supabase_auth.__version__}")
print(f"package at: {supabase_auth.__file__}")

# ---- A1/A2: storage protocol -------------------------------------------------
import supabase_auth._sync.storage as sync_storage_mod

print("\n[A1] SyncSupportedStorage module:", sync_storage_mod.__name__)
print("[A1] file:", sync_storage_mod.__file__)
print("[A1] exported names in module:", [n for n in dir(sync_storage_mod) if not n.startswith("__")])
print("[A2] is ABC?", inspect.isabstract(SyncSupportedStorage))
print("[A2] abstract methods:", sorted(getattr(SyncSupportedStorage, "__abstractmethods__", set())))
print("[A2] public callables:", [m for m in dir(SyncSupportedStorage) if not m.startswith("_")])

# ---- A3: verify_otp type literals -------------------------------------------
from supabase_auth import types as sa_types

print("\n[A3] EmailOtpType  =", sa_types.EmailOtpType)
print("[A3] VerifyEmailOtpParams =", sa_types.VerifyEmailOtpParams.__annotations__)
print("[A3] VerifyMobileOtpParams type =", sa_types.VerifyMobileOtpParams.__annotations__["type"])
print("[A3] CodeExchangeParams =", sa_types.CodeExchangeParams.__annotations__)
print("[A3] AuthFlowType =", sa_types.AuthFlowType)

# ---- A4: client method signatures -------------------------------------------
for name in ("sign_in_with_otp", "verify_otp", "resend", "sign_in_with_oauth",
             "exchange_code_for_session", "get_session"):
    fn = getattr(SyncGoTrueClient, name, None)
    print(f"\n[A4] {name}{inspect.signature(fn) if fn else '  MISSING'}")

# first docstring paragraph of the two we will call
for name in ("sign_in_with_otp", "verify_otp"):
    doc = (getattr(SyncGoTrueClient, name).__doc__ or "").strip()
    print(f"\n[A4] {name} docstring:\n{doc[:700]}")

# ---- A5: which storage keys are touched ------------------------------------
src = inspect.getsource(SyncGoTrueClient)
import re

keys = sorted(set(re.findall(r'self\._storage\.(get_item|set_item|remove_item)\(([^)]*)\)', src)))
print("\n[A5] storage call sites (method, key expr):")
for m, k in keys:
    print(f"     self._storage.{m}({k.strip()})")
print("[A5] STORAGE_KEY default:", supabase_auth.constants.STORAGE_KEY)

# ---- A6: does a FlaskSessionStorage duck-type cleanly? ----------------------
class _Probe(SyncSupportedStorage):
    def __init__(self):
        self.calls = []

    def get_item(self, key):
        self.calls.append(("get", key))
        return None

    def set_item(self, key, value):
        self.calls.append(("set", key, value))

    def remove_item(self, key):
        self.calls.append(("del", key))


probe = _Probe()
client = SyncGoTrueClient(url="https://probe.supabase.co", storage=probe,
                          flow_type="pkce", persist_session=False,
                          auto_refresh_token=False)
print("\n[A6] subclass of SyncSupportedStorage instantiates:", type(probe).__mro__[:3])
url = client.sign_in_with_oauth({"provider": "google"})
print("[A6] sign_in_with_oauth returned:", str(url)[:120], "...")
print("[A6] storage calls during PKCE authorize:", [(c[0], c[1]) for c in probe.calls])
verifier = next((c[2] for c in probe.calls if c[0] == "set"), None)
print("[A6] stored code_verifier length:", len(verifier) if verifier else None)
print("[A6] verifier is urlsafe base64 (no +,/,=):",
      bool(verifier) and all(ch not in verifier for ch in "+/="))
