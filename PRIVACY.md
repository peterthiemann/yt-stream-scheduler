---
layout: default
title: Privacy Policy | schedule-stream by Peter Thiemann
permalink: /privacy/
---

# schedule-stream by Peter Thiemann Privacy Policy

Effective November 16, 2026

schedule-stream is a command-line application that runs on your Mac. It uses YouTube API Services through the YouTube Data API v3 to find available slots, schedule unlisted YouTube Live broadcasts, and connect them to an existing reusable stream on your YouTube channel. By using schedule-stream, you agree to be bound by the [YouTube Terms of Service](https://www.youtube.com/t/terms). Google handles sign-in and processes requests to its services under the [Google Privacy Policy](https://policies.google.com/privacy).

Setup asks you to read and explicitly accept this policy before opening Google sign-in. The app records the policy version you accepted with your setup.

## Data accessed and how it is used

- **Google authorization.** The app reads the Desktop OAuth client ID and secret from the credentials file you choose. You sign in on Google's website in your browser. The app exchanges the authorization code for tokens and uses the refresh token to obtain access tokens for later runs. The app does not receive your Google password.
- **YouTube channel.** The app reads the authorized channel's display name and unique ID to show you which channel you authorized and to verify the confirmed channel before scheduling.
- **Template broadcast and stream.** The app reads the broadcast identified by the watch URL you enter, checks channel ownership, and verifies that its current bound stream can be reused. It reads broadcast metadata and settings such as description, category, scheduled times, audience designation, and streaming options to copy applicable settings to new broadcasts. It uses the current stream ID to bind broadcasts. It does not request your encoder's stream key.
- **Scheduling.** The app reads upcoming broadcast details, including IDs, titles, start times, visibility, and stream bindings, to find an open slot or recognize a matching broadcast. When you run a scheduling command, it sends the requested title, start time, unlisted visibility, and applicable template settings to YouTube and uses the template's current reusable stream to bind the broadcast. It displays the resulting watch URL in Terminal. Anyone you give the unlisted URL to can share it with others.

## Storage, security, and sharing

The app stores the OAuth client ID and secret, refresh token, accepted policy version, the channel ID you enter to confirm your channel, and the broadcast ID from the template URL you provide. It stores these in `~/Library/Application Support/schedule-stream/config.json` on your Mac until you replace or delete the setup. macOS file permissions restrict access to your user account.

The app fetches current YouTube metadata on each scheduling run, including the template settings, reusable stream ID, and upcoming broadcast list. It keeps those API responses and short-lived access tokens in memory for the run. When the updated app first opens a configuration from an earlier version, it removes the previously cached channel ID, stream ID, and template settings and requires new setup before scheduling.

The app sends authorization and scheduling data directly to Google and YouTube over HTTPS to carry out the actions above. The developer does not receive your Google user data. The app has no developer-operated server, telemetry, advertising, or tracking cookies. Any cookies used on Google's sign-in page are handled by Google.

schedule-stream uses Google user data solely to provide the channel verification, broadcast scheduling, and stream-binding features described here. Its use and transfer of information received from Google APIs adhere to the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy), including the Limited Use requirements.

## Revoke access and delete local data

1. To revoke authorization, open [Google Account permissions](https://security.google.com/settings/security/permissions), select the OAuth app you authorized for schedule-stream, and remove its access. Look for the app name shown on the Google consent screen.
2. To delete the copy of your data kept by schedule-stream, open Finder, choose **Go → Go to Folder**, and enter `~/Library/Application Support/schedule-stream/`. Move `config.json` to the Trash. For complete removal, also delete any copies of that file you made. If you revoke access, delete the local file as well.

To remove a broadcast from YouTube, use [YouTube Studio](https://studio.youtube.com/). Local file deletion removes only the copy held by schedule-stream.

## Contact

For privacy questions or complaints, contact the maintainer through the [schedule-stream issue tracker](https://github.com/peterthiemann/yt-stream-scheduler/issues). Issues are public. Keep credentials, unlisted watch URLs, and private account details out of your message.
