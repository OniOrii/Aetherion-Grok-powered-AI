# YouTube cookies for Aetherion music

Railway IPs often get YouTube's "Sign in to confirm you're not a bot" check.
Aetherion can pass your own YouTube cookies to yt-dlp so `/play` works there.

This does **not** go in git. Cookies are a login. Use a spare Google account if you can.

## What the bot reads (any one is enough)

1. `YOUTUBE_COOKIES_B64` — easiest on Railway. Base64 of a Netscape `cookies.txt`.
2. `YOUTUBE_COOKIES` — raw Netscape `cookies.txt` text (multiline).
3. `YOUTUBE_COOKIES_FILE` — path to a `cookies.txt` already on disk.

If none of these are set, music works exactly as before.

## One-time setup

1. In a desktop browser, install a cookies.txt export extension (search "Get cookies.txt LOCALLY").
2. Open YouTube while logged into a Google account you do not mind using from a server.
3. Export cookies for `youtube.com` as a Netscape `cookies.txt` file.
4. Encode that file as one line of base64.
5. In Railway → your bot service → **Variables**, add:

   `YOUTUBE_COOKIES_B64` = that single line

6. Wait until the new deploy is **Active**.
7. In Discord: `/play` a clean `https://youtu.be/VIDEOID` first.

On success the Railway logs say `youtube cookies enabled` once, then the song plays.

## When it breaks again

Cookies expire. YouTube can still block a burned IP or an account that looks automated.
Export a fresh `cookies.txt`, update the Railway variable, and redeploy.

Never paste cookies into Discord, GitHub, or the web dashboard.
