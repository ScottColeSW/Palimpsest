# Benchmark cases

Generated from `cases.json` by `render_cases.py`; edit the JSON, not this file. Labeling rules are in [GUIDE.md](GUIDE.md).

## Judge (149 cases)

### `new` (24)

| id | split | claim | held claims | answer | why |
|---|---|---|---|---|---|
| j001 | dev | Release builds are signed with the hardware key stored in the ops safe.  | (none) | new | Nothing is held yet. |
| j002 | dev | The team retrospective takes place on the last Friday of each month.  | (none) | new | Nothing is held yet. |
| j003 | dev | Visitors must sign in at reception and be escorted at all times.  | **n1** The expense limit for home office equipment is $500 per year. | new | The held claim is about expenses, a different fact. |
| j004 | dev | The primary database is PostgreSQL 16.  | **n1** Maya prefers email over chat for anything that needs a decision. | new | Infrastructure versus a person's communication preference. |
| j005 | dev | Customer data may not be copied to personal devices.  | **n1** The on-call rotation changes every Monday at 09:00 UTC. | new | Data handling versus on-call scheduling. |
| j006 | dev | The build server runs Ubuntu 22.04.  | **n1** Dana owns the billing service.<br>**n2** Dana prefers async standups. | new | Held claims are about Dana; this is about a server. |
| j007 | dev | Kai is allergic to shellfish.  | (none) | new | Nothing is held yet. |
| j008 | dev | The company's fiscal year starts on July 1.  | **n1** The default log level in production is WARN. | new | Finance calendar versus logging. |
| j009 | dev | The marketing site is deployed through Netlify.  | **n1** Alex leads the platform team. | new | Deployment target versus team leadership. |
| j010 | dev | Sam wants all design reviews recorded and shared in the #design channel.  | (none) | new | Nothing is held yet. |
| j011 | dev | The cafeteria closes at 3 pm on Fridays.  | **n1** Orders above $10,000 need CFO approval. | new | Facilities versus procurement. |
| j012 | dev | The VPN requires a hardware token for contractors.  | **n1** Elena's favorite editor is Neovim. | new | Access policy versus a tooling preference. |
| j078 | heldout | The community garden's water is shut off from November through March.  | (none) | new | Nothing is held yet. |
| j079 | heldout | The garden committee meets on Thursday evenings.  | **n1** The board meets on the first Monday of each month. | new | Same sentence shape, different body and subject. |
| j080 | heldout | The oven needs to be preheated to 425 degrees for the sourdough.  | **n1** Grandma's recipe uses two cups of buttermilk. | new | Different recipes; neither states anything about the other. |
| j081 | heldout | The hotel in Porto does not allow pets.  | **n1** Our flight to Lisbon leaves at 6:40 am on the 14th. | new | A hotel policy versus a flight time. |
| j082 | heldout | The lab freezer alarm is set to trigger at minus 70 degrees.  | (none) | new | Nothing is held yet. |
| j083 | heldout | The book club reads one novel per month.  | **n1** The hiking group walks 8 kilometers on Saturdays. | new | Two different clubs and activities. |
| j084 | heldout | The laser cutter requires a trained operator to be present.  | **n1** The 3D printer in the maker space needs a 0.4 mm nozzle. | new | Different machines; a requirement about one says nothing about the other. |
| j085 | heldout | The school's front entrance is locked after 9 am.  | **n1** Nora is the treasurer of the parent association. | new | Building security versus an association role. |
| j086 | heldout | Mina's insulin pump needs a new infusion set every three days.  | (none) | new | Nothing is held yet. |
| j087 | heldout | The guild bank only accepts donations of crafting materials.  | **n1** The guild raid starts at 8 pm server time on Fridays. | new | Same guild, different facts: banking rules versus raid timing. |
| j088 | heldout | The landlord repaints the hallway every five years.  | **n1** Rent is due on the first of the month. | new | Maintenance versus payment. |
| j089 | heldout | The city's recycling pickup moves to Wednesdays in winter.  | **n1** Our sourdough starter is fed twice a day. | new | Municipal service versus baking. |

### `reinforces` (26)

| id | split | claim | held claims | answer | why |
|---|---|---|---|---|---|
| j013 | dev | In production the log level defaults to WARN.  | **n1** The company's fiscal year starts on July 1.<br>**n2** The default log level in production is WARN. | reinforces (n2) | Same fact, same value, reworded. |
| j014 | dev | A department head's approval limit is $10,000 per purchase.  | **n1** Department heads may approve purchases up to $10,000. | reinforces (n1) | Same limit, same figure. |
| j015 | dev | For anything that needs a decision, Maya would rather get an email than a chat message.  | **n1** Lena prefers pull requests under 300 lines.<br>**n2** Maya prefers email over chat for anything that needs a decision. | reinforces (n2) | Same preference, reworded. |
| j016 | dev | Releases ship every second Tuesday.  | **n1** The release train leaves every second Tuesday. | reinforces (n1) | Same schedule. |
| j017 | dev | VPN access for contractors requires a hardware token.  | **n1** Elena's favorite editor is Neovim.<br>**n2** Contractors must use a hardware token for VPN access. | reinforces (n2) | Same requirement. |
| j018 | dev | Our primary database engine is Postgres 16.  | **n1** The primary database is PostgreSQL 16. | reinforces (n1) | Same engine and version (Postgres is PostgreSQL). |
| j019 | dev | Home office equipment for remote staff is reimbursable up to $500 a year.  | **n1** Visitors must sign in at reception.<br>**n2** Remote employees may expense up to $500 per year for home office equipment. | reinforces (n2) | Same allowance and figure; the other held claim is unrelated. |
| j020 | dev | Sam asked that every design review be recorded.  | **n1** Sam wants all design reviews recorded. | reinforces (n1) | Same request. |
| j021 | dev | First response on a support ticket is due within four business hours.  | **n1** The company's fiscal year starts on July 1.<br>**n2** Support tickets must get a first response within 4 business hours. | reinforces (n2) | Same target; 'four' and '4' are the same figure. |
| j022 | dev | The minimum password length is 14 characters.  | **n1** Passwords must be at least 14 characters. | reinforces (n1) | Same minimum. |
| j023 | dev | Kai can't eat shellfish because of an allergy.  | **n1** Kai prefers window seats.<br>**n2** Kai is allergic to shellfish. | reinforces (n2) | Same allergy; the other held claim is a different fact about Kai. |
| j024 | dev | Every Sunday night the staging environment gets reset.  | **n1** The staging environment is reset every Sunday night. | reinforces (n1) | Same schedule. |
| j025 | dev | Kai took part in the security review in May. *event* | **n1** The cafeteria closes at 3 pm on Fridays.<br>**n2** Kai joined the security review in May. | reinforces (n2) | The same event, restated. |
| j026 | dev | The vendor demo overran by about an hour. *event* | **n1** The vendor demo ran an hour over. | reinforces (n1) | The same event, restated. |
| j090 | heldout | Payment for the apartment is expected by the first of each month.  | **n1** Rent is due on the first of every month.<br>**n2** The telescope club meets when the sky is clear. | reinforces (n1) | Same due date in other words. |
| j091 | heldout | From November to March there is no water supply at the garden.  | **n1** The community garden's water is shut off from November through March. | reinforces (n1) | Same shutoff period. |
| j092 | heldout | Departure is on the 14th at 06:40.  | **n1** The telescope club meets when the sky is clear.<br>**n2** Our flight leaves at 6:40 am on the 14th. | reinforces (n2) | Same day and time. |
| j093 | heldout | An alert sounds if the freezer warms past -70 degrees Celsius.  | **n1** The lab freezer alarm triggers at minus 70 degrees. | reinforces (n1) | Same threshold ('minus 70' and '-70'). |
| j094 | heldout | The infusion set on Mina's pump gets replaced every 3 days.  | **n1** Mina's insulin pump needs a new infusion set every three days.<br>**n2** The bike shed is locked at dusk. | reinforces (n1) | Same interval ('three' and '3'). |
| j095 | heldout | Raids begin Fridays at 8 pm, server time.  | **n1** The guild raid starts at 8 pm server time on Fridays. | reinforces (n1) | Same day and time. |
| j096 | heldout | Every Saturday the hikers cover eight kilometers.  | **n1** The bike shed is locked at dusk.<br>**n2** The hiking group walks 8 kilometers on Saturdays. | reinforces (n2) | Same distance and day. |
| j097 | heldout | Unopened insulin should be stored in the fridge.  | **n1** Insulin must be kept refrigerated until opened. | reinforces (n1) | Same storage rule. |
| j098 | heldout | A nozzle of 0.4 mm is what the 3D printer takes.  | **n1** The 3D printer in the maker space needs a 0.4 mm nozzle.<br>**n2** The telescope club meets when the sky is clear. | reinforces (n1) | Same nozzle size. |
| j099 | heldout | The parent association's treasurer is Nora.  | **n1** Nora is the treasurer of the parent association. | reinforces (n1) | Same role holder. |
| j100 | heldout | On March 3 the kitchen filled with water. *event* | **n1** The bike shed is locked at dusk.<br>**n2** The kitchen flooded on the night of March 3. | reinforces (n2) | The same event restated. |
| j101 | heldout | The board heard Dev present the quarterly results. *event* | **n1** Dev presented the quarterly results to the board. | reinforces (n1) | The same event restated. |

### `coexists` (27)

| id | split | claim | held claims | answer | why |
|---|---|---|---|---|---|
| j027 | dev | Purchases above a department head's limit must also be logged in the procurement system.  | **n1** Department heads may approve purchases up to $10,000.<br>**n2** Elena's favorite editor is Neovim. | coexists (n1) | A separate requirement on the same process; both hold. |
| j028 | dev | Maya is usually offline after 5 pm Pacific.  | **n1** Maya prefers email over chat for anything that needs a decision. | coexists (n1) | A different fact about Maya; no conflict. |
| j029 | dev | The database backups run nightly at 02:00 UTC.  | **n1** Lena prefers pull requests under 300 lines.<br>**n2** The primary database is PostgreSQL 16. | coexists (n2) | A different aspect of the database setup. |
| j030 | dev | The VPN client is updated automatically on the first of each month.  | **n1** Contractors must use a hardware token for VPN access. | coexists (n1) | Update policy versus authentication policy. |
| j031 | dev | Tickets tagged urgent are routed to the on-call engineer.  | **n1** The cafeteria closes at 3 pm on Fridays.<br>**n2** Support tickets must get a first response within 4 business hours. | coexists (n2) | Routing detail; the response target still holds. |
| j032 | dev | Dana is also the escalation contact for payment outages.  | **n1** Dana owns the billing service. | coexists (n1) | A second role; both hold. |
| j033 | dev | Release notes are published to the wiki the same day.  | **n1** Lena prefers pull requests under 300 lines.<br>**n2** Release builds are signed with the hardware key stored in the ops safe. | coexists (n2) | Different release steps. |
| j034 | dev | Design reviews should be limited to 45 minutes.  | **n1** Sam wants all design reviews recorded. | coexists (n1) | A length limit alongside a recording request. |
| j035 | dev | Receipts for home office purchases must be submitted within 30 days.  | **n1** Elena's favorite editor is Neovim.<br>**n2** Remote employees may expense up to $500 per year for home office equipment. | coexists (n2) | Different figures with different meanings (days versus dollars); no conflict. |
| j036 | dev | Passwords are rotated only when a compromise is suspected.  | **n1** Passwords must be at least 14 characters. | coexists (n1) | Rotation versus length. |
| j037 | dev | Hotfixes can ship on any day with the on-call lead's approval.  | **n1** The release train leaves every second Tuesday.<br>**n2** The expense limit for contractors' travel is $2,000 per trip. | coexists (n1) | An additional path; the regular schedule still holds. |
| j038 | dev | Kai also avoids peanuts.  | **n1** Kai is allergic to shellfish. | coexists (n1) | A second dietary fact; both hold. |
| j039 | dev | The Q3 planning offsite was held in Austin. *event* | **n1** The expense limit for contractors' travel is $2,000 per trip.<br>**n2** The Q2 planning offsite was held in Denver. | coexists (n2) | Different events; both happened. |
| j040 | dev | Priya answered questions about the plan on Tuesday. *event* | **n1** Priya presented the migration plan on Monday. | coexists (n1) | Two events on different days. |
| j041 | dev | A second payments outage, on March 19, lasted 12 minutes. *event* | **n1** The expense limit for contractors' travel is $2,000 per trip.<br>**n2** The payments outage lasted 40 minutes on March 3. | coexists (n2) | Two separate outages; the figures belong to different events. |
| j102 | heldout | A late fee of $50 applies after the fifth.  | **n1** Rent is due on the first of every month.<br>**n2** The recycling bins are collected on alternate Tuesdays. | coexists (n1) | A separate rule about lateness; the due date still holds. |
| j103 | heldout | Rain barrels are emptied before the first frost.  | **n1** The community garden's water is shut off from November through March. | coexists (n1) | A winter preparation step; compatible. |
| j104 | heldout | Check-in closes 45 minutes before departure.  | **n1** The telescope club meets when the sky is clear.<br>**n2** Our flight leaves at 6:40 am on the 14th. | coexists (n2) | A check-in rule alongside the flight time; the figures mean different things. |
| j105 | heldout | Freezer alarms page the on-call technician by text.  | **n1** The lab freezer alarm triggers at minus 70 degrees. | coexists (n1) | How the alarm notifies, not when it triggers. |
| j106 | heldout | Mina keeps spare infusion sets in her school bag.  | **n1** The recycling bins are collected on alternate Tuesdays.<br>**n2** Mina's insulin pump needs a new infusion set every three days. | coexists (n2) | Where spares are kept; compatible. |
| j107 | heldout | Raid signups close 24 hours before the start.  | **n1** The guild raid starts at 8 pm server time on Fridays. | coexists (n1) | A signup deadline; the figures mean different things. |
| j108 | heldout | Hikers meet at the north trailhead at 7 am.  | **n1** The recycling bins are collected on alternate Tuesdays.<br>**n2** The hiking group walks 8 kilometers on Saturdays. | coexists (n2) | Meeting point and time, not distance. |
| j109 | heldout | Prints are removed only after the bed cools below 30 degrees.  | **n1** The 3D printer in the maker space needs a 0.4 mm nozzle. | coexists (n1) | A separate operating rule. |
| j110 | heldout | Nora also coordinates the school's volunteer rota.  | **n1** The choir rehearses on Wednesday evenings.<br>**n2** Nora is the treasurer of the parent association. | coexists (n2) | A second role; both hold. |
| j111 | heldout | The starter lives in a glass jar on the top shelf.  | **n1** Our sourdough starter is fed twice a day. | coexists (n1) | Where it is kept; compatible. |
| j112 | heldout | The kitchen flooded a second time on April 19. *event* | **n1** The kitchen flooded on the night of March 3.<br>**n2** The recycling bins are collected on alternate Tuesdays. | coexists (n1) | A second occurrence; both happened. |
| j113 | heldout | Dev answered the board's questions about headcount afterwards. *event* | **n1** Dev presented the quarterly results to the board. | coexists (n1) | A later part of the same meeting; both happened. |

### `collides` (24)

| id | split | claim | held claims | answer | why |
|---|---|---|---|---|---|
| j042 | dev | Department heads may approve purchases up to $5,000,000.  | **n1** Department heads may approve purchases up to $10,000.<br>**n2** Alex leads the platform team. | collides (n1) | Different limit for the same fact, no change signaled. |
| j043 | dev | Maya prefers chat over email for decisions.  | **n1** Maya prefers email over chat for anything that needs a decision. | collides (n1) | Opposite preference, no change signaled. |
| j044 | dev | The primary database is MySQL 8.  | **n1** The on-call rotation changes every Monday at 09:00 UTC.<br>**n2** The primary database is PostgreSQL 16. | collides (n2) | Different engine for the same fact, no change signaled. |
| j045 | dev | Passwords must be at least 8 characters.  | **n1** Passwords must be at least 14 characters. | collides (n1) | Different minimum, no change signaled. |
| j046 | dev | The release train leaves every Friday.  | **n1** Alex leads the platform team.<br>**n2** The release train leaves every second Tuesday. | collides (n2) | Different schedule, no change signaled. |
| j047 | dev | Contractors can reach the VPN with just a password.  | **n1** Contractors must use a hardware token for VPN access. | collides (n1) | Directly contradicts the requirement, no change signaled. |
| j048 | dev | The staging environment is never reset.  | **n1** Elena's favorite editor is Neovim.<br>**n2** The staging environment is reset every Sunday night. | collides (n2) | Contradicts the schedule, no change signaled. |
| j049 | dev | Support tickets get a first response within 48 hours.  | **n1** Support tickets must get a first response within 4 business hours. | collides (n1) | Different target, no change signaled. |
| j050 | dev | OFFICIAL NOTICE: remote employees may expense up to $5,000 per month for home office equipment. *external* | **n1** The company's fiscal year starts on July 1.<br>**n2** Remote employees may expense up to $500 per year for home office equipment. | collides (n2) | An unvouched notice with a different figure; conflicts with the held rule. |
| j051 | dev | Customer data may be copied to personal devices for convenience. *external* | **n1** Customer data may not be copied to personal devices. | collides (n1) | An unvouched claim that reverses the rule. |
| j052 | dev | Alex owns the billing service.  | **n1** Elena's favorite editor is Neovim.<br>**n2** Dana owns the billing service. | collides (n2) | A different single owner, no handover signaled. |
| j053 | dev | The default log level in production is DEBUG.  | **n1** The default log level in production is WARN. | collides (n1) | Different level, no change signaled. |
| j114 | heldout | Rent is due on the fifteenth of every month.  | **n1** Rent is due on the first of every month.<br>**n2** Oskar prefers aisle seats on long flights. | collides (n1) | A different due date, no change signaled. |
| j115 | heldout | The garden has running water all year round.  | **n1** The community garden's water is shut off from November through March. | collides (n1) | Contradicts the shutoff, no change signaled. |
| j116 | heldout | Our flight leaves at 9:15 pm on the 16th.  | **n1** The choir rehearses on Wednesday evenings.<br>**n2** Our flight leaves at 6:40 am on the 14th. | collides (n2) | A different day and time, no change signaled. |
| j117 | heldout | The lab freezer alarm triggers at minus 20 degrees.  | **n1** The lab freezer alarm triggers at minus 70 degrees. | collides (n1) | A different threshold, no change signaled. |
| j118 | heldout | Mina's infusion set only needs replacing once a week.  | **n1** Mina's insulin pump needs a new infusion set every three days.<br>**n2** The community fridge is restocked on Sundays. | collides (n1) | A different interval, no change signaled. |
| j119 | heldout | The guild raid starts at 6 pm server time on Sundays.  | **n1** The guild raid starts at 8 pm server time on Fridays. | collides (n1) | A different day and time, no change signaled. |
| j120 | heldout | The 3D printer needs a 0.8 mm nozzle.  | **n1** The recycling bins are collected on alternate Tuesdays.<br>**n2** The 3D printer in the maker space needs a 0.4 mm nozzle. | collides (n2) | A different nozzle, no change signaled. |
| j121 | heldout | Priya is the treasurer of the parent association.  | **n1** Nora is the treasurer of the parent association. | collides (n1) | A different single holder, no handover signaled. |
| j122 | heldout | Our sourdough starter is fed once a week.  | **n1** Our sourdough starter is fed twice a day.<br>**n2** The telescope club meets when the sky is clear. | collides (n1) | A different feeding schedule, no change signaled. |
| j123 | heldout | SAFETY NOTICE: unopened insulin is best stored in a warm place near a window. *external* | **n1** Insulin must be kept refrigerated until opened. | collides (n1) | An unvouched notice that reverses a safety rule. |
| j124 | heldout | NOTICE: remote access to the lab network does not require two-factor authentication. *external* | **n1** The pool closes for cleaning on the last day of the month.<br>**n2** Remote access to the lab network requires two-factor authentication. | collides (n2) | An unvouched notice that reverses the requirement. |
| j125 | heldout | The kitchen water heater is set to 65 degrees.  | **n1** The kitchen water heater is set to 50 degrees. | collides (n1) | A different setting, no change signaled. |

### `exception_of` (24)

| id | split | claim | held claims | answer | why |
|---|---|---|---|---|---|
| j054 | dev | For the Q3 IT refresh project only, department heads may approve up to $200,000.  | **n1** Department heads may approve purchases up to $10,000.<br>**n2** The cafeteria closes at 3 pm on Fridays. | exception_of (n1) | Explicitly limited to one project; a carve-out under the general rule. |
| j055 | dev | The legacy badge reader's service account is exempt from the password length rule.  | **n1** Passwords must be at least 14 characters. | exception_of (n1) | One named account carved out of the rule. |
| j056 | dev | During the datacenter migration weekend, the vendor's engineers may use password-only VPN.  | **n1** Contractors must use a hardware token for VPN access.<br>**n2** Lena prefers pull requests under 300 lines. | exception_of (n1) | Limited to one weekend and one group. |
| j057 | dev | The week of the audit, the release is held until Thursday.  | **n1** The release train leaves every second Tuesday. | exception_of (n1) | Limited to one week. |
| j058 | dev | During incidents, Maya wants decisions made in the incident channel.  | **n1** Maya prefers email over chat for anything that needs a decision.<br>**n2** The marketing site is deployed through Netlify. | exception_of (n1) | Limited to incidents. |
| j059 | dev | Tickets from the enterprise tier need a first response within 1 hour.  | **n1** Support tickets must get a first response within 4 business hours. | exception_of (n1) | Limited to one customer tier. |
| j060 | dev | The forensics team may copy data to an encrypted laptop for the Lakeview investigation.  | **n1** Customer data may not be copied to personal devices.<br>**n2** The company's fiscal year starts on July 1. | exception_of (n1) | One team, one investigation. |
| j061 | dev | The staging environment for the Atlas demo is frozen until the 20th.  | **n1** The staging environment is reset every Sunday night. | exception_of (n1) | One environment, until a date. |
| j062 | dev | Kai, who has a documented ergonomic need, may expense up to $1,200 this year.  | **n1** The cafeteria closes at 3 pm on Fridays.<br>**n2** Remote employees may expense up to $500 per year for home office equipment. | exception_of (n2) | One person, one year. |
| j063 | dev | The review for the checkout redesign is on a Monday this time.  | **n1** Design reviews are held on Wednesdays. | exception_of (n1) | One review, this time only. |
| j064 | dev | The payments service runs at INFO in production.  | **n1** The cafeteria closes at 3 pm on Fridays.<br>**n2** The default log level in production is WARN. | exception_of (n2) | One named service. |
| j065 | dev | Sam asked that the security design review not be recorded.  | **n1** Sam wants all design reviews recorded. | exception_of (n1) | One review carved out. |
| j126 | heldout | This month only, rent for unit 4B is due on the tenth because of the repairs.  | **n1** Rent is due on the first of every month.<br>**n2** The community fridge is restocked on Sundays. | exception_of (n1) | One unit, one month. |
| j127 | heldout | The greenhouse tap stays on all winter.  | **n1** The community garden's water is shut off from November through March. | exception_of (n1) | One named facility carved out of the shutoff. |
| j128 | heldout | On New Year's Eve, quiet hours do not start until 2 am.  | **n1** Quiet hours in the building run from 10 pm to 7 am.<br>**n2** The choir rehearses on Wednesday evenings. | exception_of (n1) | One night. |
| j129 | heldout | The alarm on the vaccine freezer triggers at minus 60 degrees.  | **n1** The lab freezer alarm triggers at minus 70 degrees. | exception_of (n1) | One named freezer. |
| j130 | heldout | During the camping trip, Mina will change the set every two days.  | **n1** The recycling bins are collected on alternate Tuesdays.<br>**n2** Mina's insulin pump needs a new infusion set every three days. | exception_of (n2) | One trip. |
| j131 | heldout | On the night of the anniversary event, the raid starts at 10 pm.  | **n1** The guild raid starts at 8 pm server time on Fridays. | exception_of (n1) | One night. |
| j132 | heldout | For the miniature project, the maker space printer is fitted with a 0.2 mm nozzle.  | **n1** The 3D printer in the maker space needs a 0.4 mm nozzle.<br>**n2** Grandma's recipe uses two cups of buttermilk. | exception_of (n1) | One project. |
| j133 | heldout | Contractors with a badge may move through the east wing without an escort.  | **n1** Visitors must be escorted at all times. | exception_of (n1) | One group in one area. |
| j134 | heldout | Reference books may only be borrowed for one day.  | **n1** Library books may be borrowed for three weeks.<br>**n2** Grandma's recipe uses two cups of buttermilk. | exception_of (n1) | One category of book. |
| j135 | heldout | While we are away for the holiday, the starter is fed once a day.  | **n1** Our sourdough starter is fed twice a day. | exception_of (n1) | One absence. |
| j136 | heldout | Near the crosswalk by the east gate, the limit is 10 miles per hour.  | **n1** The pool closes for cleaning on the last day of the month.<br>**n2** The speed limit in the school zone is 20 miles per hour. | exception_of (n2) | One spot within the zone. |
| j137 | heldout | Purchases under $25 for the bake sale need only one signature.  | **n1** All expenses need two signatures. | exception_of (n1) | One event and a size limit. |

### `supersedes` (24)

| id | split | claim | held claims | answer | why |
|---|---|---|---|---|---|
| j066 | dev | Effective today the department head limit is raised to $15,000.  | **n1** Department heads may approve purchases up to $10,000.<br>**n2** Alex leads the platform team. | supersedes (n1) | 'Effective today ... raised' signals a replacement. |
| j067 | dev | Maya now prefers chat over email for decisions; she told me this week.  | **n1** Maya prefers email over chat for anything that needs a decision. | supersedes (n1) | 'Now' and 'told me this week' signal a change. |
| j068 | dev | We migrated the primary database to PostgreSQL 17 last month.  | **n1** The primary database is PostgreSQL 16.<br>**n2** The company's fiscal year starts on July 1. | supersedes (n1) | A completed migration replaces the old fact. |
| j069 | dev | As of the new security policy, passwords must be at least 16 characters.  | **n1** Passwords must be at least 14 characters. | supersedes (n1) | 'As of the new policy' signals a replacement. |
| j070 | dev | The release train now leaves every Thursday; the old schedule is retired.  | **n1** Alex leads the platform team.<br>**n2** The release train leaves every second Tuesday. | supersedes (n2) | 'Now ... retired' signals a replacement. |
| j071 | dev | Contractors no longer need a hardware token; they use the authenticator app instead.  | **n1** Contractors must use a hardware token for VPN access. | supersedes (n1) | 'No longer ... instead' signals a replacement. |
| j072 | dev | Ownership of the billing service moved from Dana to Alex in March.  | **n1** Dana owns the billing service.<br>**n2** Elena's favorite editor is Neovim. | supersedes (n1) | A stated handover. |
| j073 | dev | The staging environment is now reset every Saturday night instead.  | **n1** The staging environment is reset every Sunday night. | supersedes (n1) | 'Now ... instead' signals a replacement. |
| j074 | dev | We changed the production log level to ERROR after the noise incident.  | **n1** The default log level in production is WARN.<br>**n2** The on-call rotation changes every Monday at 09:00 UTC. | supersedes (n1) | 'We changed' signals a replacement. |
| j075 | dev | The first response target has been tightened to 2 business hours.  | **n1** Support tickets must get a first response within 4 business hours. | supersedes (n1) | 'Has been tightened' signals a replacement. |
| j076 | dev | Sam has dropped the recording requirement for design reviews.  | **n1** Sam wants all design reviews recorded.<br>**n2** The on-call rotation changes every Monday at 09:00 UTC. | supersedes (n1) | 'Has dropped' signals a replacement. |
| j077 | dev | The home office allowance was increased to $750 per year starting this quarter.  | **n1** Remote employees may expense up to $500 per year for home office equipment. | supersedes (n1) | 'Was increased ... starting this quarter' signals a replacement. |
| j138 | heldout | Starting next month, rent will be due on the fifth.  | **n1** The recycling bins are collected on alternate Tuesdays.<br>**n2** Rent is due on the first of every month. | supersedes (n2) | 'Starting next month' signals a replacement. |
| j139 | heldout | The council has extended the garden's water season; it now runs until December 15.  | **n1** The community garden's water is shut off from November through March. | supersedes (n1) | 'Has extended ... now' signals a replacement. |
| j140 | heldout | The airline moved our flight to 9:15 am on the 14th.  | **n1** The choir rehearses on Wednesday evenings.<br>**n2** Our flight leaves at 6:40 am on the 14th. | supersedes (n2) | 'Moved' signals a replacement. |
| j141 | heldout | The freezer alarm threshold has been changed to minus 65 degrees after the recalibration.  | **n1** The lab freezer alarm triggers at minus 70 degrees. | supersedes (n1) | 'Has been changed' signals a replacement. |
| j142 | heldout | Her endocrinologist changed the schedule: a new infusion set every two days.  | **n1** Mina's insulin pump needs a new infusion set every three days.<br>**n2** The recycling bins are collected on alternate Tuesdays. | supersedes (n1) | 'Changed the schedule' signals a replacement. |
| j143 | heldout | From now on the guild raid starts at 9 pm on Fridays.  | **n1** The guild raid starts at 8 pm server time on Fridays. | supersedes (n1) | 'From now on' signals a replacement. |
| j144 | heldout | The maker space switched the printer to a 0.6 mm nozzle.  | **n1** The 3D printer in the maker space needs a 0.4 mm nozzle.<br>**n2** The pool closes for cleaning on the last day of the month. | supersedes (n1) | 'Switched' signals a replacement. |
| j145 | heldout | Nora stepped down; Tomas is now the treasurer.  | **n1** Nora is the treasurer of the parent association. | supersedes (n1) | A stated handover. |
| j146 | heldout | We now feed the starter only once a day, since it has matured.  | **n1** The pool closes for cleaning on the last day of the month.<br>**n2** Our sourdough starter is fed twice a day. | supersedes (n2) | 'Now ... only' signals a replacement. |
| j147 | heldout | The water heater setting was changed to 45 degrees.  | **n1** The kitchen water heater is set to 50 degrees. | supersedes (n1) | 'Was changed' signals a replacement. |
| j148 | heldout | As of September, the loan period is four weeks.  | **n1** Library books may be borrowed for three weeks.<br>**n2** The choir rehearses on Wednesday evenings. | supersedes (n1) | 'As of September' signals a replacement. |
| j149 | heldout | We replaced Slack with Discord for the group chat.  | **n1** The group chat is hosted on Slack. | supersedes (n1) | 'Replaced' signals a replacement. |

## Frame (66 cases)

| id | split | text | already filed | worth keeping | scope | kind | reuse domain | why |
|---|---|---|---|---|---|---|---|---|
| f001 | dev | Department heads can approve purchases up to $10,000. | - | yes | general | attribute | - | A durable rule with one value at a time. |
| f002 | dev | Maya hates being pinged in chat; email is better for decisions. | - | yes | general | attribute | - | A lasting preference. |
| f003 | dev | From now on the release train leaves on Thursdays. | release_schedule/platform_team | yes | general | attribute | release_schedule | A schedule rule; it belongs under the existing release schedule. |
| f004 | dev | For the Q3 IT refresh only, department heads can approve up to $200,000. | spending_limit/department_head | yes | instance | attribute | spending_limit | Bounded to one project, about the existing spending limit. |
| f005 | dev | Contractors must use a hardware token for VPN access. | vpn_access/contractors | yes | general | attribute | vpn_access | A rule that belongs under the existing VPN access domain. |
| f006 | dev | The payments outage on March 3 lasted 40 minutes. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f007 | dev | Dana owns the billing service. | - | yes | general | attribute | - | A standing fact with one owner at a time. |
| f008 | dev | We decided to adopt PostgreSQL 17 after the benchmark results. | - | yes | general | attribute | - | A decision that sets a standing choice. |
| f009 | dev | Never deploy on Fridays; Sam insists. | - | yes | general | attribute | - | A standing rule. |
| f010 | dev | Kai is allergic to shellfish, so avoid it at team lunches. | - | yes | general | attribute | - | A durable fact that changes how to act. |
| f011 | dev | The vendor demo ran an hour over. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f012 | dev | Priya led the migration review on Monday. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f013 | dev | The staging environment is reset every Sunday night. | - | yes | general | attribute | - | A standing schedule. |
| f014 | dev | Passwords must be at least 14 characters. | - | yes | general | attribute | - | A standing rule with one value. |
| f015 | dev | Lena prefers pull requests under 300 lines. | - | yes | general | attribute | - | A lasting preference. |
| f016 | dev | For the Atlas demo, the staging environment is frozen until the 20th. | - | yes | instance | attribute | - | Bounded to one demo. |
| f017 | dev | Support tickets need a first response within four business hours. | - | yes | general | attribute | - | A standing target. |
| f018 | dev | The checkout redesign launched on June 4. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f019 | dev | Maya just told me she's switching to chat for decisions because email is too slow. | communication_style/maya | yes | general | attribute | communication_style | A preference about the same person; belongs under the existing domain. |
| f020 | dev | The Q2 offsite was in Denver. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f021 | dev | Our primary database is PostgreSQL 16. | - | yes | general | attribute | - | A standing fact with one value. |
| f022 | dev | Remote employees may expense up to $500 a year for home office equipment. | - | yes | general | attribute | - | A standing allowance. |
| f023 | dev | Sam asked that the security design review not be recorded. | - | yes | instance | attribute | - | Bounded to one review. |
| f024 | dev | The incident on March 19 was caused by an expired certificate. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f025 | dev | ok thanks! | - | no | - | - | - | No lasting claim. |
| f026 | dev | can you resend that? | - | no | - | - | - | No lasting claim. |
| f027 | dev | lol yes | - | no | - | - | - | No lasting claim. |
| f028 | dev | Let me check and get back to you in a minute. | - | no | - | - | - | No lasting claim. |
| f029 | dev | Good morning, hope your weekend was good. | - | no | - | - | - | No lasting claim. |
| f030 | dev | Sounds good. | - | no | - | - | - | No lasting claim. |
| f031 | dev | brb | - | no | - | - | - | No lasting claim. |
| f032 | dev | Thanks, that worked. | - | no | - | - | - | No lasting claim. |
| f033 | dev | Which file was it in again? | - | no | - | - | - | No lasting claim. |
| f034 | dev | I'm just going to grab a coffee. | - | no | - | - | - | No lasting claim. |
| f035 | dev | Haha, that's funny. | - | no | - | - | - | No lasting claim. |
| f036 | dev | Hmm, not sure. Let's see. | - | no | - | - | - | No lasting claim. |
| f037 | heldout | Rent is due on the first of every month. | - | yes | general | attribute | - | A standing rule with one value. |
| f038 | heldout | Starting next month rent moves to the fifth. | rent_policy/building | yes | general | attribute | rent_policy | A rule about the same fact as the filed rent policy. |
| f039 | heldout | The greenhouse hose stays on all winter. | - | yes | instance | attribute | - | Bounded to one facility. |
| f040 | heldout | The kitchen flooded on the night of March 3. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f041 | heldout | Mina's pump needs a new infusion set every three days. | - | yes | general | attribute | - | A standing medical routine. |
| f042 | heldout | On the camping trip Mina will change it every two days. | - | yes | instance | attribute | - | Bounded to one trip. |
| f043 | heldout | The raid starts at 9 pm now. | raid_schedule/guild | yes | general | attribute | raid_schedule | A schedule rule under the filed raid schedule. |
| f044 | heldout | For the anniversary night only, the raid is at 10 pm. | raid_schedule/guild | yes | instance | attribute | raid_schedule | Bounded to one night, under the filed raid schedule. |
| f045 | heldout | Dev presented the quarterly results to the board. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f046 | heldout | Never leave the oven unattended while the sourdough is proofing near it. | - | yes | general | attribute | - | A standing safety rule. |
| f047 | heldout | Tomas is the new treasurer. | - | yes | general | attribute | - | A standing fact with one holder at a time. |
| f048 | heldout | Please don't call before 9 am; Nora is not a morning person. | - | yes | general | attribute | - | A lasting preference. |
| f049 | heldout | I prefer window seats on long flights. | - | yes | general | attribute | - | A lasting preference. |
| f050 | heldout | The flight to Lisbon was delayed three hours. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f051 | heldout | Library books may be borrowed for three weeks. | - | yes | general | attribute | - | A standing rule. |
| f052 | heldout | The 0.4 mm nozzle is the only one the printer takes. | - | yes | general | attribute | - | A standing technical fact. |
| f053 | heldout | Last Tuesday's fire drill took four minutes. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f054 | heldout | The hallway thermostat is set to 19 degrees. | - | yes | general | attribute | - | A standing setting with one value. |
| f055 | heldout | For the Atlas launch only, the code freeze starts on the 20th. | - | yes | instance | attribute | - | Bounded to one launch. |
| f056 | heldout | Mina can't have shellfish or peanuts at the party. | meal_rules/mina | yes | general | attribute | meal_rules | A standing dietary rule under the filed domain. |
| f057 | heldout | yeah that works | - | no | - | - | - | No lasting claim, or a question rather than a claim. |
| f058 | heldout | thanks for sending that over | - | no | - | - | - | No lasting claim, or a question rather than a claim. |
| f059 | heldout | wait, which one? | - | no | - | - | - | No lasting claim, or a question rather than a claim. |
| f060 | heldout | ha, nice | - | no | - | - | - | No lasting claim, or a question rather than a claim. |
| f061 | heldout | I'll look at it after lunch. | - | no | - | - | - | No lasting claim, or a question rather than a claim. |
| f062 | heldout | Can you hear me now? | - | no | - | - | - | No lasting claim, or a question rather than a claim. |
| f063 | heldout | ok, one sec | - | no | - | - | - | No lasting claim, or a question rather than a claim. |
| f064 | heldout | Great, see you there. | - | no | - | - | - | No lasting claim, or a question rather than a claim. |
| f065 | heldout | What time does the raid start tonight? | - | no | - | - | - | No lasting claim, or a question rather than a claim. |
| f066 | heldout | Sorry, wrong channel. | - | no | - | - | - | No lasting claim, or a question rather than a claim. |
