"""
FROM http://django-openid.googlecode.com/svn-history/r91/trunk/django_openid/signed.py
======================================================================================

Functions for creating and restoring url-safe signed pickled objects.

The format used looks like this:

>>> dumps("hello")
'UydoZWxsbycKcDAKLg.AfZVu7tE6T1K1AecbLiLOGSqZ-A'

There are two components here, separatad by a '.'. The first component is a 
URLsafe base64 encoded pickle of the object passed to dumps(). The second 
component is a base64 encoded SHA1 hash of "$first_component.$secret"

Calling loads(s) checks the signature BEFORE unpickling the object - 
this protects against malformed pickle attacks. If the signature fails, a 
ValueError subclass is raised (actually a BadSignature):

>>> loads('UydoZWxsbycKcDAKLg.AfZVu7tE6T1K1AecbLiLOGSqZ-A')
'hello'
>>> loads('UydoZWxsbycKcDAKLg.AfZVu7tE6T1K1AecbLiLOGSqZ-A-modified')
...
BadSignature: Signature failed: AfZVu7tE6T1K1AecbLiLOGSqZ-A-modified

You can optionally compress the pickle prior to base64 encoding it to save 
space, using the compress=True argument. This checks if compression actually
helps and only applies compression if the result is a shorter string:

>>> dumps(range(1, 10), compress=True)
'.eJzTyCkw4PI05Er0NAJiYyA2AWJTIDYDYnMgtgBiS65EPQDQyQme.EQpzZCCMd3mIa4RXDGnAuMCCAx0'

The fact that the string is compressed is signalled by the prefixed '.' at the
start of the base64 pickle.

There are 65 url-safe characters: the 64 used by url-safe base64 and the '.'. 
These functions make use of all of them.
"""

import cPickle, base64, hashlib
from django.conf import settings

def dumps(obj, secret = None, compress = False, extra_salt = ''):
    """
    Returns URL-safe, sha1 signed base64 compressed pickle. If secret is 
    None, settings.SECRET_KEY is used instead.
    
    If compress is True (not the default) checks if compressing using zlib can
    save some space. Prepends a '.' to signify compression. This is included 
    in the signature, to protect against zip bombs.
    
    extra_salt can be used to further salt the hash, in case you're worried 
    that the NSA might try to brute-force your SHA-1 protected secret.
    """
    pickled = cPickle.dumps(obj)
    is_compressed = False # Flag for if it's been compressed or not
    if compress:
        import zlib # Avoid zlib dependency unless compress is being used
        compressed = zlib.compress(pickled)
        if len(compressed) < (len(pickled) - 1):
            pickled = compressed
            is_compressed = True
    base64d = encode(pickled).strip('=')
    if is_compressed:
        base64d = '.' + base64d
    return sign(base64d, (secret or settings.SECRET_KEY) + extra_salt)

def loads(s, secret = None, extra_salt = ''):
    "Reverse of dumps(), raises ValueError if signature fails"
    if isinstance(s, unicode):
        s = s.encode('utf8') # base64 works on bytestrings, not on unicodes
    try:
        base64d = unsign(s, (secret or settings.SECRET_KEY) + extra_salt)
    except ValueError:
        raise
    decompress = False
    if base64d[0] == '.':
        # It's compressed; uncompress it first
        base64d = base64d[1:]
        decompress = True
    pickled = decode(base64d)
    if decompress:
        import zlib
        pickled = zlib.decompress(pickled)
    return cPickle.loads(pickled)

def encode(s):
    return base64.urlsafe_b64encode(s).strip('=')

def decode(s):
    return base64.urlsafe_b64decode(s + '=' * (len(s) % 4))

class BadSignature(ValueError):
    # Extends ValueError, which makes it more convenient to catch and has 
    # basically the correct semantics.
    pass

def sign(value, key = None):
    if isinstance(value, unicode):
        raise TypeError, \
            'sign() needs bytestring, not unicode: %s' % repr(value)
    if key is None:
        key = settings.SECRET_KEY
    return value + '.' + base64_sha1(value + key)

def unsign(signed_value, key = None):
    if isinstance(signed_value, unicode):
        raise TypeError, 'unsign() needs bytestring, not unicode'
    if key is None:
        key = settings.SECRET_KEY
    if not '.' in signed_value:
        raise BadSignature, 'Missing sig (no . found in value)'
    value, sig = signed_value.rsplit('.', 1)
    if base64_sha1(value + key) == sig:
        return value
    else:
        raise BadSignature, 'Signature failed: %s' % sig

def base64_sha1(s):
    return encode(hashlib.sha1(s).digest())
