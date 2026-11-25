# Mockups

`assets/mockups/screens.html` is a small library of iPhone screens rendered by headless Chrome into
transparent 1260x2640 PNGs (phone frame included). Copy it into the project with
`mockups.py --init PROJECT`, then edit the copy.

## Screens and their params
| Variant | Shows | Params |
|---|---|---|
| `paywall-features` | feature-list paywall + price selector footer | `hl=N` highlights feature row N, `price=1` outlines the monthly price in red |
| `paywall-review` | one big review as the paywall body, same footer | `price=1` |
| `onboarding-input` | text question with the iOS keyboard up ("What's your name?") | `f=<key>` from `APP.inputs`, `typed=1` shows the typed value, `step`, `of` |
| `onboarding-form` | several fields on one screen (age, weight, email) | `hl=N` focuses field N, `filled=N` fills the first N |
| `onboarding-message` | personalised reassurance screen (emoji, title, bullets) | `m=<key>` from `APP.messages` |
| `onboarding-question` | quiz step with progress bar | `q=<key>` from `APP.questions` (default `APP.question`), `sel=N` selected option, `step`, `of` |
| `onboarding-plan` | "your plan is ready" result with a chart | `full=1` full progress bar |
| `home` | app home: streak card + habit list | `hl=N` highlights habit N |
| `notification` | lock screen with a push notification | |
| `frame` | bezel only, transparent screen | for `video` layout screen recordings |

Add `&dark=1` to any variant for the dark theme (Cinematic uses dark phones throughout; the brand
green brightens and selected rows / CTAs glow).

Render: `mockups.py PROJECT/mock/screens.html PROJECT/mock "paywall-features" "paywall-features&hl=3"`.
The PNG name is the variant with `&` and `=` turned into `_` (`paywall-features_hl_3`); use that as `img`.
Check `mock/_sheet.jpg` after every render.

## Making it fit the reel
- Edit the `APP` object at the top of the script block: name, tagline, features, prices, review, quiz,
  plan, home, notification. Change `--brand` colours in `:root` to suit the topic.
- **Fictional brand** that fits the topic (a habit app, a budgeting app, a fitness app). Never a real
  company's name, logo, colours or screens.
- A screen the library doesn't have: add an entry to `S` in the script (copy the closest one). Keep the
  phone shell, status bar and 420x880 window so geometry stays the same; content lives inside `#scr`
  (378x838 CSS px). Keep text large: at reel size a phone is 600 to 700 px wide, so anything under ~13 CSS px
  is unreadable.
- Comparisons: build both versions from the same pieces (the shared `footer` on paywalls) so only the compared
  part differs.
- A hook that holds back the answer: add a skeleton version of the screen (grey blocks) with a big "?".
- Paywalls must be compliant: visible price and period, trial terms if a trial is offered, a close button, no
  countdown, no "one time offer", no "Try for $0.00".

## Geometry (for stickers in phone space)
`px`/`py` are fractions of the PNG. On the paywall screens: header and icon ~0.08 to 0.25, feature rows
~0.29 to 0.62 (row N centre ≈ 0.29 + 0.064 × (N − 1)), price selector ~0.66 to 0.76, Continue ~0.78 to 0.83.
Review paywall: stars ~0.2, quote ~0.25 to 0.5, reviewer ~0.55. Screen rect inside the PNG: x 63, y 63,
1134 × 2514, corner radius 159.

## Screen recordings
Render `frame`, then use a `video` shot with `src` pointing at the recording (any size; it is cover-cropped to
the screen). Trim with `src_in`, speed up long recordings with `speed` (e.g. 2.0).

## Quality bar for app screens

The screens are the product the viewer judges; a thin, empty or emoji-decorated screen undercuts the advice. Before a screen goes into a reel:

- **Full.** Content runs to the tab bar on every screen: a hero card, a stats row, a list of 4+ rows, a chart.
  No screen is a title and two cards on empty space.
- **Real data.** Specific numbers, names, dates, units ("185 lb", "4 sets × 8", "Nov 4", "Week 8/12"), states
  (done / current / upcoming rows), a PR badge, a progress bar part-filled. Never placeholder copy.
- **Real chrome.** Status bar (9:41, signal, wifi, battery), iOS large title or a custom header with an avatar,
  a tab bar with 4-5 labelled tabs and the active one in the brand colour, the home indicator.
- **Drawn icons** (inline SVG line icons), not emoji. No tinted circles behind icons.
- **One coherent system:** one brand colour plus one success colour, consistent radii (12-24), card borders at
  7% white on dark, tabular numbers.
- **App Store size:** 430×932 CSS at 3x = 1290×2796, so a screen can go straight into a mockup tool.
- **Headless Chrome lays out at a minimum width of about 500 px** and crops to the window: position fixed or
  absolute bars with an explicit `width` and pixel `left`, never `right: 0` or `left: 50%`.
- Look at a contact sheet of every screen at full size before using them; fix clipped or empty areas first.
