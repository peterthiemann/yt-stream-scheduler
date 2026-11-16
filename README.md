# schedule-stream

`schedule-stream` creates and binds unlisted YouTube Live broadcasts through the YouTube Data API v3. The recurring slots are Tuesday at 10:15 and Wednesday at 13:00 in `Europe/Berlin`.

Read the [Privacy Policy](https://github.com/peterthiemann/yt-stream-scheduler/blob/main/PRIVACY.md) before authorizing YouTube access.

## Install on macOS

Use Python 3.11 or later. From this directory, install the executable into your personal bin directory. Add the final line to `~/.zshrc` to keep it on your path in new Terminal sessions.

```sh
mkdir -p "$HOME/.local/bin"
install -m 755 schedule-stream "$HOME/.local/bin/schedule-stream"
export PATH="$HOME/.local/bin:$PATH"
```

## Set up once

```sh
schedule-stream setup --credentials "$HOME/Downloads/client_secret.json"
```

Keep the downloaded Desktop OAuth credentials JSON outside the project. In the browser, sign in and choose your streaming channel or Brand Account if Google presents a picker. In Terminal, check the channel's name and ID before confirming. If Google authorized the other channel, decline and restart sign-in. Then paste the watch URL from a broadcast that used your reusable encoder stream.

Setup saves your confirmed channel ID, stream ID, a snapshot of the template settings, your OAuth client details, and a refresh token in `~/Library/Application Support/schedule-stream/config.json`. The file is readable only by your macOS user. Each scheduling run obtains a fresh access token and checks the authorized channel before making changes. Run setup again to select a new template or renew authorization.

New broadcasts use the template's writable creation settings, including description, category, audience declaration, auto-start and auto-stop, DVR, embedding, recording, monitor, captions, latency, projection, and region rules when supplied. A template with a scheduled end time contributes its duration to the new slot. Studio settings outside broadcast creation, such as custom thumbnails and chat controls, aren't copied.

## Schedule

```sh
schedule-stream "Lecture 7: Type Inference"
schedule-stream "Lecture 8: Polymorphism" --dry-run --verbose
```

Without a date, the tool takes the first future slot with no scheduled broadcast on the confirmed channel. Broadcasts scheduled in YouTube Studio count even if their titles or visibility differ. Successful scheduling prints only the watch URL. Dry runs and verbose details go to stderr.

## Target or retry a specific date

Use a future Tuesday or Wednesday. If binding fails, copy the date from the error and supply the exact same title.

```sh
schedule-stream "Lecture 7: Type Inference" --date 2026-11-17 --verbose
```

A same-title unlisted broadcast in that slot is reused. If its binding is missing, the tool binds the saved stream. The tool reports a conflict if another broadcast occupies the slot or the matching broadcast uses a different stream. If YouTube's response to creation is unclear, the tool checks the same slot and tries to recover the matching broadcast. If the slot still appears empty, check it in YouTube Studio before retrying with the date and title from the error.

Protocol references from Google are available for [desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app), [broadcast listing](https://developers.google.com/youtube/data/live/reference/rest/v3/liveBroadcasts/list), [creation settings](https://developers.google.com/youtube/data/live/reference/rest/v3/liveBroadcasts/insert), [stream reuse](https://developers.google.com/youtube/data/live/reference/rest/v3/liveStreams), and [binding](https://developers.google.com/youtube/data/live/reference/rest/v3/liveBroadcasts/bind).

## Run the mocked tests

```sh
python3 -B -m unittest -v
```
