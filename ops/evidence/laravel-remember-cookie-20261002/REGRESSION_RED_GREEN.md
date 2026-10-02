# Remember-cookie regression evidence

The two feature tests send the real Laravel web guard recaller format through
cookie encryption, the `web` middleware stack, `SessionGuard`, the Eloquent
provider, and `resources/views/home.blade.php`.

The stale case first creates a user and a correctly hashed
`id|remember_token|password-hmac` recaller, deletes the matching database row,
then requests `/`. The valid case retains its matching user and token.

## Exact production baseline: Laravel 12.69.0

The tests were copied into a disposable native-Linux application built from
baseline commit `967691e7b003ba54cc42bfc5d18afc1d0a6e4d12`, exact live Composer JSON
`7098f3a19cb65f88bcc945f019dda0aa7f515737eb5d4918c30705f25c6ad872`, and
exact live lock `22af12c7e58fcfe809735dbf9955b2d22a264e9e7345cefd74398e36bf2773b9`.

- Stale cookie: failed with HTTP 500 and `TypeError: hash_equals(): Argument #1
  ($known_string) must be of type string, null given` at
  `Illuminate/Auth/SessionGuard.php:235`.
- Valid cookie: passed and authenticated through remember-me.
- Result: 2 tests, 7 assertions, 1 expected failure; exit 1.
- Committed transcript: `baseline-regression.txt`, SHA-256
  `d094ec81bdd77ef0b2f4645aa70f5edd71422cff96de14c455a2428d42404959`.

## Candidate: Laravel 12.69.1

The same tests ran against candidate lock
`77055fc8acf891496b0b356bb034d7935c04989a3751f52b788ecd1b7999206d`.

- Stale cookie: HTTP 200, `home` rendered, guest, and `viaRemember()` false.
- Valid cookie: HTTP 200, `home` rendered, matching user authenticated, and
  `viaRemember()` true.
- Result: 2 tests, 10 assertions, all passed.
- Committed transcript: `candidate-regression.txt`, SHA-256
  `e8c79ee52e118eaad16ba4085849457d8d50309000d770949dc25d0b1f5b144d`.

The baseline failure exactly reproduces the production incident. No vendor
file was edited in either environment; Composer installed each lock into a
fresh disposable application.
