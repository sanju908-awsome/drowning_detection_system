# Browser buzzer alerts

The header has an **ALARM ON/OFF** control and **TEST SOUND** button. Click **ALARM OFF · ARM** once per page session; browsers require a user gesture before they allow sound. Keep the app open, the tab unmuted, and device volume audible.

When armed, the frontend checks for newly recorded `Drowning detector` warnings every 350 ms and plays a repeated, dual-tone buzzer for the first warning. Warnings generated for a video started in the current session are eligible even if they arrive before the first incident-list refresh. Buzzer playback is deduplicated while a sound is already playing.

Browser audio is not a hardware siren and can be muted, throttled, or unavailable. CCTV currently provides a live preview only and does not generate detection events. Never rely on this prototype as the sole pool safety alarm; maintain continuous human supervision.
