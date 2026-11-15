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
