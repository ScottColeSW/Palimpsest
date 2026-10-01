# Benchmark cases

Generated from `cases.json` by `render_cases.py`; edit the JSON, not this file. Labeling rules are in [GUIDE.md](GUIDE.md).

## Judge (77 cases)

### `new` (12)

| id | split | claim | held claims | answer | why |
|---|---|---|---|---|---|
| j001 | dev | Release builds are signed with the hardware key stored in the ops safe.  | (none) | new | Nothing is held yet. |
| j002 | heldout | The team retrospective takes place on the last Friday of each month.  | (none) | new | Nothing is held yet. |
| j003 | dev | Visitors must sign in at reception and be escorted at all times.  | **n1** The expense limit for home office equipment is $500 per year. | new | The held claim is about expenses, a different fact. |
| j004 | heldout | The primary database is PostgreSQL 16.  | **n1** Maya prefers email over chat for anything that needs a decision. | new | Infrastructure versus a person's communication preference. |
| j005 | dev | Customer data may not be copied to personal devices.  | **n1** The on-call rotation changes every Monday at 09:00 UTC. | new | Data handling versus on-call scheduling. |
| j006 | heldout | The build server runs Ubuntu 22.04.  | **n1** Dana owns the billing service.<br>**n2** Dana prefers async standups. | new | Held claims are about Dana; this is about a server. |
| j007 | dev | Kai is allergic to shellfish.  | (none) | new | Nothing is held yet. |
| j008 | heldout | The company's fiscal year starts on July 1.  | **n1** The default log level in production is WARN. | new | Finance calendar versus logging. |
| j009 | dev | The marketing site is deployed through Netlify.  | **n1** Alex leads the platform team. | new | Deployment target versus team leadership. |
| j010 | heldout | Sam wants all design reviews recorded and shared in the #design channel.  | (none) | new | Nothing is held yet. |
| j011 | dev | The cafeteria closes at 3 pm on Fridays.  | **n1** Orders above $10,000 need CFO approval. | new | Facilities versus procurement. |
| j012 | heldout | The VPN requires a hardware token for contractors.  | **n1** Elena's favorite editor is Neovim. | new | Access policy versus a tooling preference. |

### `reinforces` (14)

| id | split | claim | held claims | answer | why |
|---|---|---|---|---|---|
| j013 | dev | In production the log level defaults to WARN.  | **n1** The company's fiscal year starts on July 1.<br>**n2** The default log level in production is WARN. | reinforces (n2) | Same fact, same value, reworded. |
| j014 | heldout | A department head's approval limit is $10,000 per purchase.  | **n1** Department heads may approve purchases up to $10,000. | reinforces (n1) | Same limit, same figure. |
| j015 | dev | For anything that needs a decision, Maya would rather get an email than a chat message.  | **n1** Lena prefers pull requests under 300 lines.<br>**n2** Maya prefers email over chat for anything that needs a decision. | reinforces (n2) | Same preference, reworded. |
| j016 | heldout | Releases ship every second Tuesday.  | **n1** The release train leaves every second Tuesday. | reinforces (n1) | Same schedule. |
| j017 | dev | VPN access for contractors requires a hardware token.  | **n1** Elena's favorite editor is Neovim.<br>**n2** Contractors must use a hardware token for VPN access. | reinforces (n2) | Same requirement. |
| j018 | heldout | Our primary database engine is Postgres 16.  | **n1** The primary database is PostgreSQL 16. | reinforces (n1) | Same engine and version (Postgres is PostgreSQL). |
| j019 | dev | Home office equipment for remote staff is reimbursable up to $500 a year.  | **n1** Visitors must sign in at reception.<br>**n2** Remote employees may expense up to $500 per year for home office equipment. | reinforces (n2) | Same allowance and figure; the other held claim is unrelated. |
| j020 | heldout | Sam asked that every design review be recorded.  | **n1** Sam wants all design reviews recorded. | reinforces (n1) | Same request. |
| j021 | dev | First response on a support ticket is due within four business hours.  | **n1** The company's fiscal year starts on July 1.<br>**n2** Support tickets must get a first response within 4 business hours. | reinforces (n2) | Same target; 'four' and '4' are the same figure. |
| j022 | heldout | The minimum password length is 14 characters.  | **n1** Passwords must be at least 14 characters. | reinforces (n1) | Same minimum. |
| j023 | dev | Kai can't eat shellfish because of an allergy.  | **n1** Kai prefers window seats.<br>**n2** Kai is allergic to shellfish. | reinforces (n2) | Same allergy; the other held claim is a different fact about Kai. |
| j024 | heldout | Every Sunday night the staging environment gets reset.  | **n1** The staging environment is reset every Sunday night. | reinforces (n1) | Same schedule. |
| j025 | dev | Kai took part in the security review in May. *event* | **n1** The cafeteria closes at 3 pm on Fridays.<br>**n2** Kai joined the security review in May. | reinforces (n2) | The same event, restated. |
| j026 | heldout | The vendor demo overran by about an hour. *event* | **n1** The vendor demo ran an hour over. | reinforces (n1) | The same event, restated. |

### `coexists` (15)

| id | split | claim | held claims | answer | why |
|---|---|---|---|---|---|
| j027 | dev | Purchases above a department head's limit must also be logged in the procurement system.  | **n1** Department heads may approve purchases up to $10,000.<br>**n2** Elena's favorite editor is Neovim. | coexists (n1) | A separate requirement on the same process; both hold. |
| j028 | heldout | Maya is usually offline after 5 pm Pacific.  | **n1** Maya prefers email over chat for anything that needs a decision. | coexists (n1) | A different fact about Maya; no conflict. |
| j029 | dev | The database backups run nightly at 02:00 UTC.  | **n1** Lena prefers pull requests under 300 lines.<br>**n2** The primary database is PostgreSQL 16. | coexists (n2) | A different aspect of the database setup. |
| j030 | heldout | The VPN client is updated automatically on the first of each month.  | **n1** Contractors must use a hardware token for VPN access. | coexists (n1) | Update policy versus authentication policy. |
| j031 | dev | Tickets tagged urgent are routed to the on-call engineer.  | **n1** The cafeteria closes at 3 pm on Fridays.<br>**n2** Support tickets must get a first response within 4 business hours. | coexists (n2) | Routing detail; the response target still holds. |
| j032 | heldout | Dana is also the escalation contact for payment outages.  | **n1** Dana owns the billing service. | coexists (n1) | A second role; both hold. |
| j033 | dev | Release notes are published to the wiki the same day.  | **n1** Lena prefers pull requests under 300 lines.<br>**n2** Release builds are signed with the hardware key stored in the ops safe. | coexists (n2) | Different release steps. |
| j034 | heldout | Design reviews should be limited to 45 minutes.  | **n1** Sam wants all design reviews recorded. | coexists (n1) | A length limit alongside a recording request. |
| j035 | dev | Receipts for home office purchases must be submitted within 30 days.  | **n1** Elena's favorite editor is Neovim.<br>**n2** Remote employees may expense up to $500 per year for home office equipment. | coexists (n2) | Different figures with different meanings (days versus dollars); no conflict. |
| j036 | heldout | Passwords are rotated only when a compromise is suspected.  | **n1** Passwords must be at least 14 characters. | coexists (n1) | Rotation versus length. |
| j037 | dev | Hotfixes can ship on any day with the on-call lead's approval.  | **n1** The release train leaves every second Tuesday.<br>**n2** The expense limit for contractors' travel is $2,000 per trip. | coexists (n1) | An additional path; the regular schedule still holds. |
| j038 | heldout | Kai also avoids peanuts.  | **n1** Kai is allergic to shellfish. | coexists (n1) | A second dietary fact; both hold. |
| j039 | dev | The Q3 planning offsite was held in Austin. *event* | **n1** The expense limit for contractors' travel is $2,000 per trip.<br>**n2** The Q2 planning offsite was held in Denver. | coexists (n2) | Different events; both happened. |
| j040 | heldout | Priya answered questions about the plan on Tuesday. *event* | **n1** Priya presented the migration plan on Monday. | coexists (n1) | Two events on different days. |
| j041 | dev | A second payments outage, on March 19, lasted 12 minutes. *event* | **n1** The expense limit for contractors' travel is $2,000 per trip.<br>**n2** The payments outage lasted 40 minutes on March 3. | coexists (n2) | Two separate outages; the figures belong to different events. |

### `collides` (12)

| id | split | claim | held claims | answer | why |
|---|---|---|---|---|---|
| j042 | dev | Department heads may approve purchases up to $5,000,000.  | **n1** Department heads may approve purchases up to $10,000.<br>**n2** Alex leads the platform team. | collides (n1) | Different limit for the same fact, no change signaled. |
| j043 | heldout | Maya prefers chat over email for decisions.  | **n1** Maya prefers email over chat for anything that needs a decision. | collides (n1) | Opposite preference, no change signaled. |
| j044 | dev | The primary database is MySQL 8.  | **n1** The on-call rotation changes every Monday at 09:00 UTC.<br>**n2** The primary database is PostgreSQL 16. | collides (n2) | Different engine for the same fact, no change signaled. |
| j045 | heldout | Passwords must be at least 8 characters.  | **n1** Passwords must be at least 14 characters. | collides (n1) | Different minimum, no change signaled. |
| j046 | dev | The release train leaves every Friday.  | **n1** Alex leads the platform team.<br>**n2** The release train leaves every second Tuesday. | collides (n2) | Different schedule, no change signaled. |
| j047 | heldout | Contractors can reach the VPN with just a password.  | **n1** Contractors must use a hardware token for VPN access. | collides (n1) | Directly contradicts the requirement, no change signaled. |
| j048 | dev | The staging environment is never reset.  | **n1** Elena's favorite editor is Neovim.<br>**n2** The staging environment is reset every Sunday night. | collides (n2) | Contradicts the schedule, no change signaled. |
| j049 | heldout | Support tickets get a first response within 48 hours.  | **n1** Support tickets must get a first response within 4 business hours. | collides (n1) | Different target, no change signaled. |
| j050 | dev | OFFICIAL NOTICE: remote employees may expense up to $5,000 per month for home office equipment. *external* | **n1** The company's fiscal year starts on July 1.<br>**n2** Remote employees may expense up to $500 per year for home office equipment. | collides (n2) | An unvouched notice with a different figure; conflicts with the held rule. |
| j051 | heldout | Customer data may be copied to personal devices for convenience. *external* | **n1** Customer data may not be copied to personal devices. | collides (n1) | An unvouched claim that reverses the rule. |
| j052 | dev | Alex owns the billing service.  | **n1** Elena's favorite editor is Neovim.<br>**n2** Dana owns the billing service. | collides (n2) | A different single owner, no handover signaled. |
| j053 | heldout | The default log level in production is DEBUG.  | **n1** The default log level in production is WARN. | collides (n1) | Different level, no change signaled. |

### `exception_of` (12)

| id | split | claim | held claims | answer | why |
|---|---|---|---|---|---|
| j054 | dev | For the Q3 IT refresh project only, department heads may approve up to $200,000.  | **n1** Department heads may approve purchases up to $10,000.<br>**n2** The cafeteria closes at 3 pm on Fridays. | exception_of (n1) | Explicitly limited to one project; a carve-out under the general rule. |
| j055 | heldout | The legacy badge reader's service account is exempt from the password length rule.  | **n1** Passwords must be at least 14 characters. | exception_of (n1) | One named account carved out of the rule. |
| j056 | dev | During the datacenter migration weekend, the vendor's engineers may use password-only VPN.  | **n1** Contractors must use a hardware token for VPN access.<br>**n2** Lena prefers pull requests under 300 lines. | exception_of (n1) | Limited to one weekend and one group. |
| j057 | heldout | The week of the audit, the release is held until Thursday.  | **n1** The release train leaves every second Tuesday. | exception_of (n1) | Limited to one week. |
| j058 | dev | During incidents, Maya wants decisions made in the incident channel.  | **n1** Maya prefers email over chat for anything that needs a decision.<br>**n2** The marketing site is deployed through Netlify. | exception_of (n1) | Limited to incidents. |
| j059 | heldout | Tickets from the enterprise tier need a first response within 1 hour.  | **n1** Support tickets must get a first response within 4 business hours. | exception_of (n1) | Limited to one customer tier. |
| j060 | dev | The forensics team may copy data to an encrypted laptop for the Lakeview investigation.  | **n1** Customer data may not be copied to personal devices.<br>**n2** The company's fiscal year starts on July 1. | exception_of (n1) | One team, one investigation. |
| j061 | heldout | The staging environment for the Atlas demo is frozen until the 20th.  | **n1** The staging environment is reset every Sunday night. | exception_of (n1) | One environment, until a date. |
| j062 | dev | Kai, who has a documented ergonomic need, may expense up to $1,200 this year.  | **n1** The cafeteria closes at 3 pm on Fridays.<br>**n2** Remote employees may expense up to $500 per year for home office equipment. | exception_of (n2) | One person, one year. |
| j063 | heldout | The review for the checkout redesign is on a Monday this time.  | **n1** Design reviews are held on Wednesdays. | exception_of (n1) | One review, this time only. |
| j064 | dev | The payments service runs at INFO in production.  | **n1** The cafeteria closes at 3 pm on Fridays.<br>**n2** The default log level in production is WARN. | exception_of (n2) | One named service. |
| j065 | heldout | Sam asked that the security design review not be recorded.  | **n1** Sam wants all design reviews recorded. | exception_of (n1) | One review carved out. |

### `supersedes` (12)

| id | split | claim | held claims | answer | why |
|---|---|---|---|---|---|
| j066 | dev | Effective today the department head limit is raised to $15,000.  | **n1** Department heads may approve purchases up to $10,000.<br>**n2** Alex leads the platform team. | supersedes (n1) | 'Effective today ... raised' signals a replacement. |
| j067 | heldout | Maya now prefers chat over email for decisions; she told me this week.  | **n1** Maya prefers email over chat for anything that needs a decision. | supersedes (n1) | 'Now' and 'told me this week' signal a change. |
| j068 | dev | We migrated the primary database to PostgreSQL 17 last month.  | **n1** The primary database is PostgreSQL 16.<br>**n2** The company's fiscal year starts on July 1. | supersedes (n1) | A completed migration replaces the old fact. |
| j069 | heldout | As of the new security policy, passwords must be at least 16 characters.  | **n1** Passwords must be at least 14 characters. | supersedes (n1) | 'As of the new policy' signals a replacement. |
| j070 | dev | The release train now leaves every Thursday; the old schedule is retired.  | **n1** Alex leads the platform team.<br>**n2** The release train leaves every second Tuesday. | supersedes (n2) | 'Now ... retired' signals a replacement. |
| j071 | heldout | Contractors no longer need a hardware token; they use the authenticator app instead.  | **n1** Contractors must use a hardware token for VPN access. | supersedes (n1) | 'No longer ... instead' signals a replacement. |
| j072 | dev | Ownership of the billing service moved from Dana to Alex in March.  | **n1** Dana owns the billing service.<br>**n2** Elena's favorite editor is Neovim. | supersedes (n1) | A stated handover. |
| j073 | heldout | The staging environment is now reset every Saturday night instead.  | **n1** The staging environment is reset every Sunday night. | supersedes (n1) | 'Now ... instead' signals a replacement. |
| j074 | dev | We changed the production log level to ERROR after the noise incident.  | **n1** The default log level in production is WARN.<br>**n2** The on-call rotation changes every Monday at 09:00 UTC. | supersedes (n1) | 'We changed' signals a replacement. |
| j075 | heldout | The first response target has been tightened to 2 business hours.  | **n1** Support tickets must get a first response within 4 business hours. | supersedes (n1) | 'Has been tightened' signals a replacement. |
| j076 | dev | Sam has dropped the recording requirement for design reviews.  | **n1** Sam wants all design reviews recorded.<br>**n2** The on-call rotation changes every Monday at 09:00 UTC. | supersedes (n1) | 'Has dropped' signals a replacement. |
| j077 | heldout | The home office allowance was increased to $750 per year starting this quarter.  | **n1** Remote employees may expense up to $500 per year for home office equipment. | supersedes (n1) | 'Was increased ... starting this quarter' signals a replacement. |

## Frame (36 cases)

| id | split | text | already filed | worth keeping | scope | kind | reuse domain | why |
|---|---|---|---|---|---|---|---|---|
| f001 | dev | Department heads can approve purchases up to $10,000. | - | yes | general | attribute | - | A durable rule with one value at a time. |
| f002 | heldout | Maya hates being pinged in chat; email is better for decisions. | - | yes | general | attribute | - | A lasting preference. |
| f003 | dev | From now on the release train leaves on Thursdays. | release_schedule/platform_team | yes | general | attribute | release_schedule | A schedule rule; it belongs under the existing release schedule. |
| f004 | heldout | For the Q3 IT refresh only, department heads can approve up to $200,000. | spending_limit/department_head | yes | instance | attribute | spending_limit | Bounded to one project, about the existing spending limit. |
| f005 | dev | Contractors must use a hardware token for VPN access. | vpn_access/contractors | yes | general | attribute | vpn_access | A rule that belongs under the existing VPN access domain. |
| f006 | heldout | The payments outage on March 3 lasted 40 minutes. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f007 | dev | Dana owns the billing service. | - | yes | general | attribute | - | A standing fact with one owner at a time. |
| f008 | heldout | We decided to adopt PostgreSQL 17 after the benchmark results. | - | yes | general | attribute | - | A decision that sets a standing choice. |
| f009 | dev | Never deploy on Fridays; Sam insists. | - | yes | general | attribute | - | A standing rule. |
| f010 | heldout | Kai is allergic to shellfish, so avoid it at team lunches. | - | yes | general | attribute | - | A durable fact that changes how to act. |
| f011 | dev | The vendor demo ran an hour over. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f012 | heldout | Priya led the migration review on Monday. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f013 | dev | The staging environment is reset every Sunday night. | - | yes | general | attribute | - | A standing schedule. |
| f014 | heldout | Passwords must be at least 14 characters. | - | yes | general | attribute | - | A standing rule with one value. |
| f015 | dev | Lena prefers pull requests under 300 lines. | - | yes | general | attribute | - | A lasting preference. |
| f016 | heldout | For the Atlas demo, the staging environment is frozen until the 20th. | - | yes | instance | attribute | - | Bounded to one demo. |
| f017 | dev | Support tickets need a first response within four business hours. | - | yes | general | attribute | - | A standing target. |
| f018 | heldout | The checkout redesign launched on June 4. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f019 | dev | Maya just told me she's switching to chat for decisions because email is too slow. | communication_style/maya | yes | general | attribute | communication_style | A preference about the same person; belongs under the existing domain. |
| f020 | heldout | The Q2 offsite was in Denver. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f021 | dev | Our primary database is PostgreSQL 16. | - | yes | general | attribute | - | A standing fact with one value. |
| f022 | heldout | Remote employees may expense up to $500 a year for home office equipment. | - | yes | general | attribute | - | A standing allowance. |
| f023 | dev | Sam asked that the security design review not be recorded. | - | yes | instance | attribute | - | Bounded to one review. |
| f024 | heldout | The incident on March 19 was caused by an expired certificate. | - | yes | instance | event | - | One occasion; a thing that happened. |
| f025 | dev | ok thanks! | - | no | - | - | - | No lasting claim. |
| f026 | heldout | can you resend that? | - | no | - | - | - | No lasting claim. |
| f027 | dev | lol yes | - | no | - | - | - | No lasting claim. |
| f028 | heldout | Let me check and get back to you in a minute. | - | no | - | - | - | No lasting claim. |
| f029 | dev | Good morning, hope your weekend was good. | - | no | - | - | - | No lasting claim. |
| f030 | heldout | Sounds good. | - | no | - | - | - | No lasting claim. |
| f031 | dev | brb | - | no | - | - | - | No lasting claim. |
| f032 | heldout | Thanks, that worked. | - | no | - | - | - | No lasting claim. |
| f033 | dev | Which file was it in again? | - | no | - | - | - | No lasting claim. |
| f034 | heldout | I'm just going to grab a coffee. | - | no | - | - | - | No lasting claim. |
| f035 | dev | Haha, that's funny. | - | no | - | - | - | No lasting claim. |
| f036 | heldout | Hmm, not sure. Let's see. | - | no | - | - | - | No lasting claim. |
