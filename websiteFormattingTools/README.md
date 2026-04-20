# Website Formatting Tools

Optional files for hosting the generated stats output on an Apache or
LiteSpeed webserver. They (a) harden the site with security headers and
(b) replace Apache's default directory listing with a styled version.

Not required to generate stats — skip this directory if you're not
self-hosting on Apache/LiteSpeed. nginx ignores `.htaccess`; set the
equivalent directives in your `server` block instead (see main
[README.md](../README.md) Hardening section).

## Files

| File | Purpose |
|------|---------|
| `.htaccess` | Security headers + directory-index styling |
| `sh5-index.css` | Stylesheet for the directory-index listing |

## Setup (one-time)

Assuming your stats land under `/home/<user>/public_html/sh5/` and are
served at `https://yoursite.example/sh5/`:

```bash
scp .htaccess sh5-index.css yourhost:public_html/sh5/
```

That's it. Every future stats upload under `sh5/` inherits the
hardening and the styled listing automatically — no per-upload step.

## What you'll see

**Security headers** (verify with `curl -I`):

```
x-frame-options: DENY
content-security-policy: frame-ancestors 'none';
x-content-type-options: nosniff
referrer-policy: strict-origin-when-cross-origin
```

**Directory listing at `/sh5/`** — subdirectories sorted newest-first,
no truncated names, no empty Size column, CSS/.htaccess hidden from
the table.

## Requirements

- Apache with `mod_headers` and `mod_autoindex` enabled. Most shared
  hosts have both on by default.
- `AllowOverride` must permit `FileInfo` and `Indexes` (or `All`) on
  the `sh5/` tree. If the `.htaccess` seems ignored, ask the host to
  enable it.

## Adjusting

- Change the link color scheme: edit `#2563eb` in `sh5-index.css`.
- Change listing sort: edit `IndexOrderDefault` in `.htaccess`
  (e.g. `Ascending Date`).
- Hide additional files: append names to `IndexIgnore` in `.htaccess`.
- Apply to a directory other than `sh5/`: update the `IndexStyleSheet`
  path in `.htaccess` to match the new location.
