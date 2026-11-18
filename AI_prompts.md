# Final Project (Steelman Ballot): AI prompt log

This log lists the prompts I gave the AI coding assistant while designing and building Steelman Ballot, in my own words and in order. The full plan lives in `../final project brainstorm/plan.md`.

<!-- Template:
## Step N: Title
**Prompt (my own words):** "..."
**Follow-up prompt:** "..." (if needed)
**What was lacking before:** one sentence
-->

## Step 1: Problem and sources
**Prompt (my own words):** "my problem is as a us citizen and voter, i dont know where and how to gather enough information on what issues are at stake on the ballot, what are the different stances, the pros/cons/for which groups/impacts of the vote, and what the differnt poltciians and positions stand for. i saw these are sources any us citizen anywhere in the country can access. i want to build a muklti-agent process that can look into these sources and consolidate a simple dashboard for a curious voter to review and get up to date on what matters most. whta are your reocmmendations for best user-friendliness and impact?"
**What was lacking before:** There was no project idea, only the required report sections.

## Step 2: Look-back and forward-looking test cases
**Prompt (my own words):** "would it be helpful to do a 'look back' on the recent 2026 midterms election? and that can also test the accuracy of what we are trying to do with app, and then do a forward-looking one? i am curious baout the maojr swings for georgia or texas, or major jursidictions like california, or stick local like nyc."
**Follow-up prompt:** "i want the app to be functional for all states/jurisdictions/etc., so this is just to show an example?"
**What was lacking before:** There was no way to measure accuracy, and it wasn't clear that the example states were test cases rather than limits.

## Step 3: Freshness and caching
**Prompt (my own words):** "would it be an issue if you can't pull up to date data"
**Follow-up prompt:** "yes. and i want daily refreshes, or whatever timeframe you reocmmend for cache refresh and if already pulled from same jursidction to use same run for that day, unless something refeshed that day if easy to tell"
**What was lacking before:** There was no plan for stale data or for sharing one research run across voters in the same jurisdiction.

## Step 4: Name, tagline and steelmanning
**Prompt (my own words):** "steelman vs strawman arguemnt. i want more intellectual discussion and debate and engaement and discuourse. maybe will integrate 1) social feed posting to X and instagram. and for comments, requires acknowledging strongest point on other side, before can comment further. or maybe this comment debate style stipulation is own separate app idea"
**Follow-up prompt:** "steelman ballot is available, let's do that. and no need fo steelman challenge. just the steelman both sides on card. move ahead"
**What was lacking before:** The cards listed pros and cons but had no test that each side was stated at its strongest, and the first names were already taken.

## Step 5: Steelman method and election guardrails
**Prompt (my own words):** "what is the metholdogy of the steelman argument?"
**Follow-up prompt:** "Yes. before you do - anything else to consider from best practices in campaigning / polling / debate / intellectual discussion / etc. you reocmmend to implement or create guardrails against?" and then "do all the star items if not already in the plan add them. and language access - add spanish and mandarin, and another language if you recommend.  anything else you reocmmemnd to be most user friendl, accurate, and helpful for mission of best lowdown and arguments on both sides voter issue tool?"
**What was lacking before:** The steelman had no written method or tests, and the plan was missing protections against order effects, false balance, wrong voting instructions, persuasion and unequal treatment of candidates, as well as any language access.

## Step 6: Security against tampering and hacking
**Prompt (my own words):** "anything to guard against from potential tampering, hacking, coding tricks from ai scraping, etc. to icnlude?"
**What was lacking before:** The plan covered errors and bias but not deliberate attacks: poisoned or fake sources, injection hidden in scraped pages, bots running up costs, the shared cache spreading one bad run, and doctored screenshots.

## Step 7: FEC and Congress.gov adapters
**Prompt (my own words):** "Yes, start" (approving the next build step: the OpenFEC and Congress.gov adapters for each candidate's "Funded by" and "Did" sections)
**What was lacking before:** The app could find an address's districts but couldn't yet say who funds a federal candidate or what a sitting member of Congress has done.

## Step 8: Open States adapter for state legislators
**Prompt (my own words):** "Yes, start" (approving the Open States adapter for state legislators' "Did" section)
**What was lacking before:** The app covered members of Congress but not the state house and senate members on most ballots, and honorary resolutions were crowding out real bills.

## Step 9: First agents (Ballot Mapper and Measure Analyst)
**Prompt (my own words):** "Yes, start" (approving the first agents: the Ballot Mapper and the Measure Analyst, starting with the California look-back)
**What was lacking before:** The app had data sources but no agents, no card format, and no protection for reading web pages: hidden-text injection, look-alike sites, made-up citations or misquotes.

## Step 10: Critic and Candidate Profiler
**Prompt (my own words):** "Yes, start" (approving the Critic, which runs the steelman tests and sends cards back for rewrites, and the Candidate Profiler for the Says / Did / Funded by cards)
**What was lacking before:** Nothing tested the cards for strawmen, one-sided wording, unsupported claims or vote recommendations, and the app had no candidate cards.

## Step 11: Cost-effective evaluation and model choice
**Prompt (my own words):** "is this best aprocah or do you hvae more cost effective recomendation"
**Follow-up prompt:** "yes" and then "what is lowest model to stil accurately and efficeintly get what you're looking for? i imagine the steelman argument creator and processes raound that should at least be at the model they're set at; is other info scraping okay to use lower token cost models? what do you reocmmend?"
**What was lacking before:** Statewide measures were cached per district combination (so they'd be re-researched many times), page menus and footers were sent to the model, there was no independent accuracy score, and there was no evidence on whether a cheaper writer model hurts quality.

## Step 12: Better argument coverage, final model setup, mobile and chat sharing
**Prompt (my own words):** "implement these suggestions: A prompt tweak asking for each side's top three official points may help. The Grader runs on the same model as the writer. Classmate fairness ratings would add an independent check."
**Follow-up prompt:** "ignore the classmate fairness rating kit. just build with top models for reasoning for greatest accuracy at reaosnable tokens, as you found. ocmmit. i also want this to be mobile app friendly and good for whatsapp and wechat"
**What was lacking before:** Steelmen covered only about 76% of the official arguments' key points, the model choices weren't settled, and there was no way to share a card in WhatsApp or WeChat without risking one-sided sharing.

## Step 13: Cards built around "what changes", one headline per side, on the merits only
**Prompt (my own words):** "before you push wha would it take to 95%+? or another best practice percentage to reach?"
**Follow-up prompt:** "i dont want to get into motivations or claims about donors, but rather, focus on what the change is from current state to proposed future state - what do you recommend to focus more on that?", then "is it possible to just list one key point for steelman argument rather than 3+ points, or what is best practice here", then "anything else to complete sa well before moving forward?" and "yes"
**What was lacking before:** Cards didn't show today vs. if-it-passes side by side, led with several points instead of one clear headline per side, sometimes carried arguments about motives or donors, had no reading-level check, and were scored by a single grading pass.

## Step 14: Dashboard (mobile-first web app)
**Prompt (my own words):** "Build dashboard meanwhile" (while the class Portkey key was at its usage limit)
**What was lacking before:** The cards existed only as JSON files. There was no way for a voter to enter an address, see their ballot, read the cards on a phone, or share a card in WhatsApp or WeChat.

## Step 15: Massachusetts and New York, live ballot lookup, and the "Patina & Paper" redesign
**Prompt (my own words):** "no texas, but all of new york please along with al of california nad massachuasetts / if anyone enters the address it would cover it? / ... a visual of the us states with shaded in for the states we do cover / a section on steelman vs strawman argument, an "About Us" / "Our Philosophy" section of the site / "How we Work" - a methodology section, in plain english / how do you think of these mottos/slogans? THINK MORE DEEPLY. VOTE MORE THOUGHTFULLY. The strongest argument isn't always your own. Explore the most compelling perspectives on the issues that matter. Challenge your assumptions without abandoning your values. / visually show the two sides of each ballot issue with little weight judgmenet fairness iconography and in a simple plain enlgish statement below each ... Steelman Ballot — Patina & Paper (design brief: EB Garamond + IBM Plex Sans; Verdigris #234742, Uncoated Paper #F4F0E7, Graphite #2B3031, Aged Copper #AD7857, Weathered Steel #A9B0AB; no partisan colors)"
**Follow-up prompt:** "should the project just focus on ballots, not candidates? ... would it be useful to sample vote throug hthe balots ... and then shake out who my top 1-2 candidates may be" and "is it possible that this refreshes / pulls the balots live when you enter a relevant address rather htan having set up alrady?"
**What was lacking before:** Only California was covered, there was no visual of coverage, no explanation of the method or the idea behind steelmanning, and the design didn't express balance between the two sides.

## Step 16: Both sides first, side by side
**Prompt (my own words):** "remove the "what matters most to you" sectoin on site, it's not that helpful to whta we're aiming to do. when clicking into each proposition, odn't put yes or no on top of ecah other, but rather side by side. include iconography of the weight fairness measure logo with each yes and no vote stance. same with the what would change section, from left to right, share today and arrow visual to if it passes. basically but each side at its strongest at the top and make horizontal rather than vertically stacked - i want that to be first headline takeaway, with option to scroll down below if interested"
**What was lacking before:** On phones the two sides were stacked, so one always came first; the card opened with yes/no text instead of the two cases; and "What would change" didn't read as a before-and-after.

## Step 17: One consistent left/right rule on every card
**Prompt (my own words):** "is the order logical with strongest case for vs against, yes vote means vs no vote, and today vs if it passes - last section today vs if it psases is basically no to yes vote on right side? what order do you reocmmend for all /modifing anything if you changed anything"
**What was lacking before:** The two sides and the yes/no boxes alternated by measure number while "Today → If it passes" was fixed, so on odd-numbered measures Yes sat on the left at the top and on the right at the bottom.

## Step 18: Own API key, Connecticut, batch research, Spanish and Chinese
**Prompt (my own words):** "how to increase my ai access?" then "great. just added my own open ai key. continue the reminaing things to finish. i also want to add connecticut state." and "just added crdits to api"
**What was lacking before:** The app could only use the class Portkey key (at its limit), there was no way to research many contests at once with a spending cap, Connecticut wasn't covered, and nothing was translated.

## Step 19: Research every remaining contest and publish
**Prompt (my own words):** "push it when done"
**What was lacking before:** Only 6 California props and 2 races had cards; Massachusetts, New York City and the rest of California showed "Research pending", nothing was translated, and one California sample card was still unverified.

## Step 20: User-testing kit
**Prompt (my own words):** "i also will bring back in user feedback per class instructions + what would best opitimize and get feedbcak for this app, bring it back in" then "great. push the latest"
**What was lacking before:** No structured way to test the app with real users, so the report had no real-user evidence on time saved, understanding, fairness or ease of use.

## Step 21: Example addresses showing the wrong state; no total reading time
**Prompt (my own words):** "The Try an Example section is linke to the wrong places (Scaramento links to MA etc.) can you check again. also i want to remove the time to read all ballot cards, since some people may skim more and the full length of time may be discouraging"
**What was lacking before:** A new lookup left the previous address's ballot on screen while loading, and a slower earlier lookup could overwrite a newer one; the summary also showed a total reading time that could discourage people.

## Step 22: Philosophy page icons and tighter copy
**Prompt (my own words):** "i don't mind the "your ballot in 60 seconds" - i don't like the "35 min total read for all ballots" / on the "our philosophy page" can you include a little iconography next to each bullet of "what we believe"? / any way to make it even more concise while still compelling? can keep as is as well"
**What was lacking before:** The beliefs were a plain text list, and the page ran longer than it needed to.

## Step 23: Fixes from a harsh-TA and busy-voter review
**Prompt (my own words):** "if you reviewed the whole site as both a harsh ta as well as a time-short potentially interested voter trying to understand what's on the ballot, review whole site pages and let me know feedback and how would score/grade" then "Yes, fix them"
**What was lacking before:** Copper labels failed WCAG contrast (3.3:1), the sticky phone header took a sixth of the screen, the ballot summary showed 9 pills and 3 notices before any measure, unresearched races were a list of dead ends, the two sides started halfway down a phone screen, and the home page didn't say the ballot was a look-back demo.

## Step 24: Home page order, Connecticut town questions, live progress
**Prompt (my own words):** "on front page, there are 3 sections listed - I what would change II both sides at strongest III your decision - is order actualy both sides at strongest, then what would change, on actual individual ballots? if so, please make correct order on home page / what would it take to cover town charter questions in ct? is that reasonably feasible? give me breakdown and analysis for this mission and tokens and accuracy, and rec to do or not / when entering address and clicking see my ballot, can you create a loading bar and have it reflect the status of the loading? i want more transpraency int he backend preocess for users to see it's coming just nto yet, rather than indefinite waiting time, or to see stale former address info below if pulled different address eaarlier."
**What was lacking before:** The home page listed the card sections in a different order than the cards use, there was no assessment of Connecticut town questions, and a lookup showed only "Finding your districts…" with no sense of progress.

## Step 25: Privacy-first search bar, ZIP-only option, a real steelman example
**Prompt (my own words):** "steelman vs strawman example - more compelling option (can use one of the actual past ballot responses already tested and cleared)? got to make a great first impression on the concept / for home address, what is 'minimum' info address needed? do you need the zip code, state, etc. for example? / under the home address bar, make the note of 'never stored' even more prominent and first thing, communicate the privacy factor here more. several users didn't want to use actual home address. come up with transparent concise messaging around this search bar, and within the search bar or also added clear insturctions, on whta is minium address info needed"
**What was lacking before:** The privacy promise was a small hint, addresses were sent in the URL (so server logs could keep them), there was no option for people unwilling to share a street address, and the steelman example was a made-up bus-lane line instead of the app's own tested cards.

## Step 26: Anonymous usage totals
**Prompt (my own words):** "can i see how many users have tested it / how many unique addresses have been entered?" then "yes" (to anonymous counters) and "for 'never stored', change to 'we never store addresses' and don't need to mention we count totals"
**What was lacking before:** Because addresses and access logs are never kept, there was no way to see whether anyone used the app at all.

## Step 27: Report-an-issue form without a GitHub account
**Prompt (my own words):** "if someone reports an issue, how would i be notified? i see it brings it to github to create an issue" then "created the form: ... can you take a quick look and see if any changes or looks good, and tell me how to edit the design to match the website a bit more?"
**What was lacking before:** Reporting a problem required a GitHub account, which most voters don't have, and reports didn't say which card they were about.

## Step 28: Clear call to action on each measure; a calmer home page
**Prompt (my own words):** "for each ballot, i know i can click in to see more. one user didn't know to click more. can you include text of instead of "both sides checked", to "click to view each side" or "click to read more" ... something more steelman per the nmission/site, similar language with the call to action clearly and concisely? / the top front section looks quite busy. if it were my first time using the site, i wonder how it can be more crystal clear what is happening while not being overwhelming with things ot read? ... open to your anlaysis and recommendations"
**What was lacking before:** Measure rows ended with a status badge instead of telling people to tap, and the top of the home page had about 150 words in 8 blocks without a plain sentence saying what the site does.

## Step 29: Card order that puts the evidence next to the disagreement
**Prompt (my own words):** "is it true that each ballot will only have vote yes or no? in that case, both sides and language around two sides makes sense. if there would be a reason not to, then 'all sides / each sides' language can fit. keep consistent. ... for actual balllot page, do you think the order of information and visualization of the info makes sense? ... the evidence often has hidden gems locked in for the discerning voter, like in california bilionaires tax, mentioning that there may be some loss of income if implemented ..."
**What was lacking before:** The crux and the evidence sat near the bottom of each card, after the mechanics, so the facts that settle or sharpen the disagreement were easy to miss; labels said "prediction" and "value"; and some cards showed "Placed on ballot by: Not specified".

## Step 30: How we work, for every state
**Prompt (my own words):** "for how we work section, it says california specific info. do you want to make more general by state"
**What was lacking before:** The sources and accuracy steps read as California-only, and step 3 still used the old fact / prediction / value labels.

## Step 31: One AI writes, a second AI stress-tests
**Prompt (my own words):** "wouldit be more compelling in the how section to merge III and IV, because some may balk at AI drafting the card... but extra air tight to have a 2nd AI test that one... one user was pleasantly surprised and even impressed about the 2nd ai testing the other, so i want to merge that together as the compelling part of process. collectively it is ai writing - and re-writing / strress testing - of what gets written on the card"
**What was lacking before:** "An AI drafts the card" stood alone as its own step, inviting skepticism, while the reassuring part (a second AI trying to break it) came separately afterward.

## Step 32: Writer and challenger, both clearly AI
**Prompt (my own words):** "Make it clearer that the writer (first) is AI a swell, while the second one is specifically called AI. the first line is a little long, feel fee to break it up. 4 out of 5 reference doesnt include contetx of scoring system, give more info. i liked the fuller explanation you had before. i just wanted to combine this section where the first part is a really robust writing process and scoring etc. while the second part is the stress-test / challenge / testing by a whole other ai to be a supporter who would sign off as this is their best argument put forth"
**What was lacking before:** Only the reviewer was named as AI, the writer's description was one long sentence, and "below 4 out of 5" had no scale to explain it.

## Step 33: Home page: covered states under the address box; shorter lines
**Prompt (my own words):** "On homepage, can you remove the "try" line? intead create new line underneath the address line, with the states this is eligible for" then "FOr this section - can you make even more concise? The strongest argument isn't always your own. Enter your address to see what's on your ballot, and the strongest case for each side." and "does this section best convey the mission/philosophy or would you reword at all? Think more deeply. Vote more thoughtfully."
**What was lacking before:** The example-address line added clutter without saying where the app works, the purpose line repeated what the address box already implies, and the placeholder was cut off on phones.

## Step 34: "How a card works" above the map, matching the card
**Prompt (my own words):** "is this section on front page in the best section or where would it make most logical and user friendly sense? I Both sides, at their strongest ... II What would change ... III Your decision ..."
**What was lacking before:** The three-step explainer sat below the coverage map, so first-time visitors saw coverage before learning what a card shows, and step II still described the old card order.

## Step 35: A new visit starts blank
**Prompt (my own words):** "if opening new page should front pgae be blank with any ballots or last search / claifornia results? the how we work section is back to 6 steps not sure if you reocmmend that or if some recent changes got lots"
**What was lacking before:** Every visit re-showed the last lookup's ballot (confusing for first-timers and testers, and visible to the next person on a shared device), and an old cached stylesheet could still show How we work's nested bullets as extra numbered steps.

## Step 36: The address box and the result stand out
**Prompt (my own words):** "i feel like the privacy bar is almost more higlighted than the search bar itself. shodl the search bar have a thicker dark gold or whatever reocmmened accent color or ismply as bolded or more bolded as the privacy bar around it so it's the clear call to action? i don't mind the privacy bar being as apparent as it is given user concerns / when it does generate should the your ballot in 60 seconds be even more apparent as the main output deliverable and to know to scroll down and view more in that area, perhaps also bolder or with some accent or somtehing else to draw more attention"
**What was lacking before:** The address box had a thin border and looked weaker than the privacy note beside it, and the "Your ballot in 60 seconds" summary did not read as the main result or point people to the measures below it.

## Step 37: Say plainly what the site is (and is not)
**Prompt (my own words):** "for the 'see your balot, with strongest case...' shold i emphase strongest case for each side as that main value of the site? one user who enlgihs wasnt so easy for them was confused and thought this was a voting polling site, i want to make it clear that this is steelman concept arguments to better understand what's on the ballot, to get informed..."
**What was lacking before:** The purpose line did not stress the steelman idea, and nothing told visitors that this is a guide to read, not a poll or a place to vote. That confused a tester whose first language is not English.

## Step 38: The full 1–5 scale, with 4 as the pass line
**Prompt (my own words):** "In the how we work setion, the scale of 1-5 only shows 1, 3, 5 - is that ok? othewise would someone be confused about it scoring 4 and what that means as it needs to get that minimum score?"
**What was lacking before:** The scale defined only 1, 3 and 5, yet the pass rule was "4 or 5", so readers could not tell what a 4 meant. The challenger's own rubric had the same gap. Both now define all five points.

## Step 39: One job per page, and a home page that links to each
**Prompt (my own words):** "I really adore the Steelman vs Strawman section of the site as it shows the crux of the concept and how we work. there is the other section of howe we work and the philosophy. is any of this ovrelapping /redundant to point of not being most useful and efficient? what is best structure for sections and what to include in each? would you rerder/group anything or keep as is?" then "before restructuring, is there anything on home page as well that shold be considered in this like the states of what we cover or the steps I II and III on the front page?" and "Yes, include them"
**What was lacking before:** The same points (how steelmen are tested, on the merits, equal treatment, never recommending, privacy) were repeated across three or four pages, and the Steelman page's copy of the scoring rule had already gone out of date. The home page previews didn't link to the pages that explain them, and coverage was described three different ways: the map said "any U.S. address", but a ZIP outside the four states is turned away (only a street address shows districts and races).

## Step 40: The result shows without scrolling
**Prompt (my own words):** "i want to compress the beginning part of home page so the ballot in 60 seconds shows when it's done running - without needing to scroll - to make as user friendly and inutitive as posisble. make necessary adjustments you'd reocmmend"
**What was lacking before:** After a lookup, the full intro (headline, motto, purpose lines, coverage line) stayed above the result, so "Your ballot in 60 seconds" started below the fold on a laptop and needed a scroll on a phone.

## Step 41: A first-time voter's review, all eight fixes
**Prompt (my own words):** "pretend you're a ui design expert and civic engagement advocate and geniune voter who is not in the know. comb through site and make a list of any potential upgrades/recommendations if would meaningfully improve or keep as is if none no problem" then "Do all 1–8"
**What was lacking before:** Race cards showed placeholder lines ("Funded by: state campaign finance not connected yet") and called a 20-year congressman someone with "no legislative record"; California listed a U.S. Senate race that isn't on its 2026 ballot; the summary counted uncovered races as if they had cards; reading 14 propositions meant going back to the list after each one, with no sign of which were already read; dates showed as 2026-11-03; the phone menu cut off "Our philosophy"; and "Look-back demo" didn't say plainly that the election had already happened.

## Step 42: "Ready" while typing, "Matched to" on the result
**Prompt (my own words):** "when type in address shuold it show drpo down of matching address or some way to confirm the info is all set and ready to click see my ballot" then "maybe just Looks complete: a small ✓ "Ready" next to the button? or would you recommend differently" and "Ready + matched address"
**What was lacking before:** Nothing told voters their entry was complete before clicking, or which address the Census actually matched afterward. We chose not to add an autocomplete dropdown, because it would send every keystroke of a partial address to a third party, which conflicts with "We never store addresses."

## Step 43: Keep the free server awake
**Prompt (my own words):** "push any other recommendations we haven't pushed yet" then "yes implement. also what about the voter user experience recommendations, did we implement those"
**What was lacking before:** Render's free plan puts the site to sleep after about 15 idle minutes, so the first visitor after a quiet spell (a tester, or a TA opening the link) waited 30–60 seconds on a blank page.

## Step 44: Steelman front and center; one About page; translations, QR, and voting next steps
**Prompt (my own words):** "i want to convey steelman concept front and center, succinctly and crystal clearly for any layperson, on front pgae. and i want to combine the about us / philosophy / steelman vs strawman pages (more of the steelman vs strawman may be coverd on front page where the main concept can move). that is where the name comes from and crux and unique framework of the whole app. the other pages take focus away from main point of the app, whihc is the balot tool / the spanish and mandarin language pgaes on front page show the ballot issue names in enlglish rather than the other language, can you correct? and where else this may be an issue? / connecticut doesnt seem to work right now so you can actually completely remove that state for now. / when no races come up and it says "null", can you rename to something more 'plain english' to an actual voter? / at the end of any ballot issue speicifc pgae, at bottom, can you share a quick concise note on how to actually vote on the proposal... without telling how/what to vote of course / ...when you click "not right?" or "edit", did not pup up a box or link to let users modify or edit the address or zip code there... what do you propose as solution? / for the chinese version part, item below WeChat button as shown seems to need a QR code... do i need to make a wechat account or something in order to make link that will open there?"
**What was lacking before:** The steelman idea lived on its own page, and there were three info pages competing with the ballot tool. The ballot list, card numbers, race and district names and several labels stayed in English on the Spanish and Chinese pages, and Chinese money amounts read "$11.25 billion". The WeChat QR image was broken on every page, because the SVG lacked the header browsers need. A stray "null" appeared on ZIP lookups. Connecticut showed nothing useful. Cards ended without saying how voting on a measure actually works. "Edit" sent voters to the top of the page without them noticing.

## Step 45: Clearer method, and the Ready check in the edit box
**Prompt (my own words):** "for the address editing, within the ballot after "not right / edit?" the address bar that shows doesnt do the check that the above address box offers; would i tmake sense to have it here in a feasible reaosnable way as well? / does wechat qr code link update to real site once i push, not just local host as shown in example here? / on the how we work page, on swap test, can you make clear that it is swapping the 'supporters position' or someting like that regrading the yes/no labels or clarify that meaning? / for IV we measure accurayc, where do 'each side's top points covered' come from / is validated by / who says it's the top point?the first AI writer? and the "we" in we measure accuracy - who is we referring to? can add this clarity / Under About us, how we test every steelman, it junmps into "a second AI plays a committed supporter..." without first discussing if/what a first AI does. / the V keep it fresh and safe, would it be helpful to include the address anonymity here?... / II we read only official and nonpartisan sources - love this section. i wonder if it's possible to hvae the state by state info as a drop down to reveal rather than show outright so all the steps are viewable at a glance... i think the 2 AI roles are a fascinating part of this to hgihlight from first skim"
**What was lacking before:** The in-place address box had no Ready check. "Swap test" didn't say what was swapped. The accuracy step didn't say who "we" was, which cards were tested, or who decides a side's "top points" (answer: each side's own official argument, ranked by a separate test-only grader before it sees the card). The About page introduced the challenger before the writer. Step V promised "safe" without mentioning the address. The state-by-state table pushed the two-AI step below the fold.

## Step 46: A calmer hero
**Prompt (my own words):** "for this section, is this too busy on front page above address entry box? [The strongest argument isn't always your own. / Understand what's on your ballot: the strongest case for each side (a "steelman"), side by side. / A guide to read before you vote. This is not a poll, and you can't vote here.]" then "Yes, trim it"
**What was lacking before:** Three lines of text sat between the headline and the address box, and "(a 'steelman')" interrupted the main sentence, even though the steelman section right under the box now explains the word.
