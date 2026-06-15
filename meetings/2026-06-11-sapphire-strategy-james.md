# Meeting — Sapphire prompts, models, and data integration strategy with James

- **Date:** 2026-06-11
- **Granola notes:** https://notes.granola.ai/t/b3fa429e-b21c-4fd3-aa84-34f602d86e89-008umkv4 *(auth-gated; transcript below is the record of substance)*
- **Participants:** Rohan Arya Gondi, James (Quiver leadership)
- **Why this matters:** this is the meeting that defines how James wants the Feb-2026 Sapphire prompt corpus used. The whole `sapphire-capability-map` repo is the execution of it.

---

## Structured notes (derived)

### James' methodology (what the Feb-2026 folder is)
Persona → prompt → pipeline → tool-frequency. He built ~59 fake-but-real-mandate exec personas, had each generate the prompts they'd ask of Sapphire (299 total), expanded every prompt into a uniform 6-stage "pipeline" (inputs, tools called, sub-prompts, outputs), then ran a frequency analysis across all pipelines to find the most-used external tools/data — the prioritized integration list.

### The three-layer data vision (the strategic frame)
1. **Internal (moat):** Quiver's unique EP-CRISPR functional data — novel target signals nobody else has.
2. **Context:** external data Quiver *can't* know (safety/contraindication, prevalence, competition) — gates go/no-go. "A target may be great for pain but cause cancer → no-go; Quiver data won't know that."
3. **Predictivity / boosting:** independent corroboration (genetics, PPI, pathway, transcriptomic signatures) that *re-ranks* hits. The #7 → #1 example: a target ranked #7 by Quiver that independently appears in an academic screen + interacts with the disease gene gets promoted to #1.

### Key decisions / asks
- **Build out "the table"** (task → capability → which model solves it → gap). Be ambitious, 100+ rows. → delivered as `capability_map.xlsx`.
- **Convert personas to markdown.** → delivered in `personas/`.
- **Expert-agent idea (James' headline):** emulate a $50k CNS regulatory/clinical expert from their *public* output (blogs, podcasts, tweets). Rohan's analog: financial-market sentiment/prediction bots — "change stocks to biology." → scoped + scaffolded in `expert-agent/`.
- **Hayes' task:** think about cutting-edge agentic *orchestration* for Sapphire — not "Emit 2.0," something novel that privileges Quiver's data. → `orchestration_brief_hayes.md`.
- **Secret project (James + Marty + Matt):** rank haploinsufficiency CRISPR hits (125 of ~1500 meaningful signatures are haploinsufficient) by commercial attractiveness using Claude.

### Timeline
- **Tue 2026-06-11 eve:** earlier-week deliverables (trace-based embeddings, Emit testing, MAMMAL vs Boltz benchmark, haploinsufficiency commercial ranking).
- **Tue (following week):** review the full capability table with James + Gavin.
- **Before Fri (following week):** present the "master plan of all the models and what they can do."

### Action items
- Rohan: build out the capability table (done → this repo), schedule the Tue review w/ Gavin, gather prompts to find Emit's limits, send the demo email.
- Rohan + Hayes: explore the stock-market-bot → biology analog for the expert agent.
- James: share the Box folder + readings (the Feb-2026 corpus, now in `source/`).

---

## Full transcript (verbatim)

> Format note: "Them" = James, "Me" = Rohan. Lightly punctuated auto-transcript.

**Them:** Quiver. Angelini.
**Me:** It looks like you've been a quiver for a while.
**Them:** Dude, this is nothing. I have, like. Yeah, this is nothing. Angel, this. This might be helpful person. A. Because I could share these. Then I'll actually just save you time.
**Me:** Oh, if you've already built out the personas that you like, then I can just plug them. Yeah.
**Them:** Correct. Exactly. Exactly. Exactly. You'll need to make markdowns of them.
**Me:** Yeah, that's true.
**Them:** Is this it? No. Hold on one second, guys. This is important. Angelini. I'm concerned that. Actually.
**Me:** James for future note, this would be perfect for claw to do. Because it'll just go search your files. For specific keywords that you want to do, and it'll go.
**Them:** Yeah, it's so. Thank you. That's good to know. It's funny because. It. This is evidence of, like, the cognitive burden to incorporating things like that into your workflow and, like, how hard it is to overcome habit. Right? Like, I have habits for claude. And I've not yet. Like, the first thought is not to use claude for the. For this particular thing, right? Ange. What the. Pfizer. Let me look up fizer. It. I'm. I don't. So. So it should be on my desktop, and I clean my desktop occasionally. So one thing could happen is it got moved into a different folder, but itself is a phone list for claude.
**Me:** It's fine. I mean, whenever you find, oh, there we go.
**Them:** This would be. Yeah, this is. This is the one sapphire prompt. Work February 2026. So I have. All these personas. That, like, have a set of. So you have to turn these into markdowns. I made them as. As. As word documents.
**Me:** Yeah.
**Them:** But, like, it gives you some sense of, like, what they do. These are fake people. They have, like, this is what they're. It's based on, like, the companies. Like mandates. And, like, each company has different philosophy. So they have.
**Me:** I've done this before. When I was doing, I've done this exact thing once.
**Them:** Okay, so let me give you. Let me give you this, and we can.
**Me:** Yeah.
**Them:** Then you would use those to build out that table. You can give it 100 rows. Or more. I mean, okay, like, let's not be. Let's be ambitious here. And then we figure out all the models that. That. That could solve them. And then actually, the places where there's no models to solve them, maybe we can consider building our own, like, curated corpus of knowledge that can help at least do a good job for that thing that's missing.
**Me:** Okay.
**Them:** Okay.
**Me:** Right now, like, if you were to just look at, like, I can just share it again. What we. Have on this table, right? If we were to get this up more, like what would be like the 10th one that you would add, for example, because what you said yesterday, but like, you know, ask cloud, like what things to like, what capabilities you want, like would we need it for quiver? I did ask that and then it made this and then, you know, found a bunch of models, tested some of them, blah, blah, blah. What would you add?
**Them:** So here's. Here's. Here's, like, some other. And these are not. Let's not even just say I'm just going to list other important things and whether it's a model or not. TBD. Patient prevalence. Genetic variants. Like disease Association. So is a gene associated with a disease? These are not necessarily models. Some of these will be knowledge graphs and data sets.
**Me:** Yeah, I think most of what you're saying right now would be like an amit question.
**Them:** Okay, well, but how good is it that. Yeah, exactly. Exactly.
**Me:** Again, we can test it out and we'll see how it performs. Yeah.
**Them:** Other things you'd want to do.
**Me:** So actually if you have prom.
**Them:** Protein. Protein interaction.
**Me:** Pt.
**Them:** Yeah, I have problems I can share my Pro. That's another good. I have prompts. Yeah, I do have prompts. I have hundreds.
**Me:** S. Like proms for like emit that you want to test out because you have.
**Them:** Well, here's what actually. So you don't even need to ask anyone prompts. I'll just send. So let me just share what I have again, because I did this all for Angelina. So I have is. See, again, I'm not coder, but I do. I do.
**Me:** Pretty tough.
**Them:** Know. I like to think that if you. If you're just joking, then leave me alone. But if you're being serious, I would say then. Then, like, I'm. I'm proud that you. I'm proud that you think that. So when I. I made all these personas, and then when I asked the personas to do is to say.
**Me:** No, no, no. I was being serious. You do.
**Them:** What prompts would you ask. Of sapphire? And so I have all these prompts there. Somes are specific to common nodes. Using this. There's a hundred of them. Okay. There's all these problem. S.
**Me:** For internal data?
**Them:** Yes and no, but it should still give you a sense because it's not just internal data. It's internal data plus external data and stuff. So it's not just internal.
**Me:** This could be something that we. Try out with. We could try this out with emmet at the demo maybe. Like we can discuss how that would work because I don't know if the would just right now completely flop when trying to identify internal data as well.
**Them:** Oh, sorry. Sure.
**Me:** You know, because it.
**Them:** So. So then. Right. So then what you do is you. So then what I did is I actually looked at the. So then I. Then for each of those prompts. I created a. Pipeline for every single one of the prompts, one through 100.
**Me:** S defined by a plane here.
**Them:** Actually one through 300. And they give you the. And they're all uniform. It gives you exactly the inputs. And the tools it would call. And the sub prompts.
**Me:** So it's like a log of what it did.
**Them:** It's sort of what athlete is going to be more flexible than this. But yes, ultimately sort of the types of things it could do for every single prompt because all the prompts are different. And then I had claude go through all of those and generate a tool frequency. Just to understand some of the things that are most commonly used across all those prompts. So anyway, I will share this. I can share this whole folder on box.
**Me:** In the entire folder.
**Them:** And then you should dig around and use it.
**Me:** Yeah. Okay. But coming back. Sorry, coming back to like what we want to do. For tomorrow. Do you think it. S still, at least I think it's still useful to go to each person and get their personal comps.
**Them:** Yeah, go ahead. Go ahead. So I think let me just recap for tomorrow. You're going to have some updates on the trace based stuff. You're going to have a slide or two on em. It. Which is mostly like here's all the things that was really good at. We were excited. We. All the people we provide these prompts from the whole team. I went and tried them out. They did a good job. We have a call scheduled for one o'clock on Tuesday to the demo the better paid version. We'll report back next Friday. That's sort of the. So you have trace base, emit. Mammal. You'll show mammal versus bolts, which I thought is really exciting. You can mention as a next step, hey, and hope better if ben gets you to today and you can say, hey, we, we thought maybe this could help us with tse2. So bent send me these strings and the compounds. And now we tested them. Oh, look, it actually did a pretty good job. And I think that should be it for tomorrow.
**Me:** What about the table like I already have with, you know, a bunch of tasks, how things are doing because I'll build that up a lot more because I just started doing that yesterday.
**Them:** That I would say. So that's, this is one of the things, which is. That I want to be more thoughtful of. And that what we discussed, plus what matt's going to show is already. And we have all this that Caitlyn and team are going to show for, like, commercially, commercially attractive. So you guys don't know this, but in parallel yesterday, I asked the team to query the crisper data set. There's 125 hits. There's, there's like three 1500 hits. But of the 1500 hits in the crisp, meaning signatures that were like meaningful 125 of them are haploinsufficient. Associated with haploid sufficient disorders, meaning that when you knock that gene down, it causes the disease, which means we can make relevant predictions about targets that might rescue that haploinsufficient disorder. So the team generated a list of top 10, 20 and 50. Predicted genes. They're antipodal to the hit that we suspect would rescue. That haploinsufficiency. And then me and Marty and Matt are going to use claude to rank those hits by commercial attractiveness. Is anyone else developing a drug on that hit? Is that an interesting Target? You know, is in the pathway, you know, all these questions that might, that might be really interesting to, like, a business development or pharma person. So that's a hugely packaged end there for tomorrow evening. I want next week to present this other stuff of the full table to say we dug in since last week. We start to explore all the models for all these different questions. We've identified all the ones we like the most and etc, etc, etc. So I would say you can build out the table today, Rohan, as you make your other slides. And then get us together on. I'm out for a funeral on Monday. But guests together on Tuesday. It's our, it's, it's okay. Just to be clear, my 95 year old grandmother passed away. It's sad.
**Me:** Oh. I'm so sorry.
**Them:** Yeah. Yeah. It's okay. She was amazingly, she lives amazing life. It wasn't abrupt. I feel okay about it. I'll see my cousins, which I'm happy about. And, yeah, she, when you're 95, you're not the same as.
**Me:** This kind of happened. Yeah, not a mystery.
**Them:** She, she was calling her. There were days where she was, I think she probably didn't even know who I was. You know, she's fine. She, like, kind of knew who I was, but, like, it's not the same. Right. So, like, you're like, she just wants to, like, watch TV and, you know, so. My mom's very sad. That's what mostly is, is making me sad. But I appreciate the condolences. I'm feeling good. I'm, you know, I'm, I'm, I'm glad she can be at peace. So I'll be out Monday. But Tuesday, let's have a meeting to, like, I'm hyped about this. So, like, let's build out the table and then let's review it together on Tuesday. Us plus Gavin. And then I'll come with my secret project. And I can, I need, I'll need your guys help because I think there's, I think my versions of e 0.1, I think there can be a, even better version with your guys help given you guys know a lot more about how to build these things than me. So let's do that and then Go before next Friday to present our master plan of all the models and what they can do.
**Me:** Got it. James, before you go, James Rohan, how can I get involved? What can I do to help before meeting on Tuesday?
**Them:** That's a great question.
**Me:** You know, you can get emit and you can test it out yourself as well. Yeah, I think that's.
**Them:** Well, well, so actually.
**Me:** How you just keep doing.
**Them:** I, I think, no, I think there's, I think there's a better use of, of hay's time because, like, Emmett, I kind of get it, Rohan. You'll test it. And, like, the, the question is, like, is it good? And I don't know if Hayes is the right person to know if it's good. Like, you can test it wrong. You'll have to share it with other people to see if they like the answers. So, like, other people doing that is not going to be that helpful. One thing I'm just thinking is.
**Me:** Yeah, yeah, obviously.
**Them:** I really liked some of the engineering and architecture you were commenting on yesterday, Hayes, for your, your tool. So maybe what you can do for Tuesday, which is going to require me to find a little bit of time today to send you some materials is. Like, consider some of the orchestration for sapphire. Like, as Rohan's billing at the table, like, how might we string together those things with our data? And then, you know, There's a simple answer, which is. Like, yeah, agent calls tools, but there's more sophisticated ways. I can imagine we can be doing this. And so doing some thinking about what are our options for the most cutting edge valid. Ways to be using these tools? Maybe that's a way, you know, like we want to build something that's not emit 2.0. With our data. We want something that's has our data, has something very different than emit and, and maybe even more novel. So maybe thinking about what creative builds. Pays could be valuable here.
**Me:** One thing I'll say, James, is that on their image announcement, they said they can integrate internal data with emit. So one question that immediately raised was would this model run locally because in a quiver data and all that.
**Them:** Yeah, that's why I think, David, that's what David's thinking. Yeah.
**Me:** So again, question for then. But if they present a compelling view for how they would integrate corporate data with their data. A lot of. The work would be done for us kind of, you know.
**Them:** And so that's why I think, I think actually, ultimately, that's why David shared it, is the ability to tap it in. I think, David thinks this could just replace everything that expo is doing with Paul because it's.
**Me:** I'm thinking as well.
**Them:** Like, that's why he's, that's what he thinks is like, and, and, like, the thing, and Paul said this last week himself, which is like every month a new tool like this is going to come out. Every month. That's why we should keep building out the table and we should be. And actually, did you check X to see if there's anyone else publishing? Like the other thing, actually, another thing to look at, hey, is this paperclip pubmed thing.
**Me:** As I had that on my list of things to, because I was trying to like benchmark like emit versus like, you know, paperclip versus like just vanilla clawed and have.
**Them:** Okay. Yeah. Yeah. Like, I'm gonna give you an example. I'm gonna give you an example for the two of you and, and Rohan. I know you and, oh, you know, even a couple weeks, I know you, and I know you're gonna be excited to go explore this. But you have other work to do. So, like, focus. It doesn't mean I don't want you to, like, limit you. So if you want to be up till 5am and explore, you, you should. I mean, it's such an exciting time. But, hey, this is something that you could also be doing giving some of your time to help for Tuesday, which is. There's a lot. So you guys know what we're trying to do. We have a unique data set that can provide novel insights to the brain, like targets. About, about sodium targets for pain. That no one's ever thought of because they've been, like, appearing in our screens and we have our data suggested they're really important. And you wouldn't find that in the literature. So, like, there's a unique layer. Everything else, there's two other layers for why what we don't, what we need to touch on our data. That are external. External data and external tools. One are sets of tools. That. Will help the context for those predictions. If a prediction for a target of pain is the most amazing target for pain theoretically. But it ultimately, you know, pain will be, it'll solve all of pain. But that Target is known to cause cancer. It's a no go. Quiver's data will not know if that target causes cancer. It will only know that that. Correct. So there's, so there's connections that add context to our hypotheses.
**Me:** Which is why.
**Them:** And then there's tools and data that add predictivity. And, and sorting, better sorting of our hypotheses. So, for instance, imagine we have 10 predictions for genes or targets that would rescue. Dupe 15q. Outside of ub3. Totally novel. We still think it could be disease modifying. And our data suggests that the number one ranking prediction is gene y. And then there's, you know, prediction B and C and D and E and F and, and F is actually gene X. So in our ranking gene X is like number seven. However, maybe some of the other data sets and the other tools. Might have found in the supplemental data of some paper or in some RNA sequencing data set that gene seven interacts directly with ub3. And it was a hit on someone's screen in academic lab that no one cared about. You might rank that now number one. Because it appeared separately in two different types of assays for the same target. That's like highly compelling evidence. So you may use that evidence to say, oh, the ranking purely from quiver is not. We, you know, the addition of this extra context re ranks number seven to be number one. So there's data that provide context for decision making and there's data that provides boosting of predictivity of matching. And, and so one where I'm going with this is like one thing that I've been thinking of is. There is a. We, there's a company that, that was off. They have like 10 people of, of farm farma experts. With like 20 years experience in CNS. Regulatory experience about how to gauge the FDA, what's the right safety studies, how you design clinical trials, and you have to pay them like $50,000 for their expertise. I believe very strongly. That we could find. Public. Posts, blog posts, tweets, podcasts. Of those types of experts where they've given us all of their knowledge for free. And we can build an agent. Who can do just as good. As Sally from Pfizer with 25 years experience because Jenny. Was posting all about her, her lessons and her knowledge and her wisdom on Twitter for the past 10 years.
**Me:** Yeah, I see the vision here. I think the analogous thing that I think has already been built out is for like stock markets when you have prediction bots that do semantic analysis, they go through all this. Information and that's how you build it. So yeah, what could be interesting is to look through how they've built that out and then just change stocks to biology.
**Them:** Yeah. So we need to do that, right? Because like. Yeah. Let's, so let's, maybe you and Hayes can explore that. That sounds a great idea. Let's not reinvent the wheel, but there's so many much publicly available knowledge that's highly specialized knowledge that is not, like, obvious biotech data. It's not neural data, it's not cellular data, it's not gene data, it is, but it's very important decision making data for drugs and targets.
**Me:** My. One. Concern maybe would be. The sort of. Cost or time or that kind of stuff with ingesting the data. Because if you have like we'd either need to. Have priors about where the information isn't filter hard to get those and then ingest, which is already bad or you do like a lot of figure out if it's reliable or not.
**Them:** So. Rohan. Well, so, so listen, listen. This is the type of thinking we could do next week on Tuesday. That's what I'm saying, which is like those all, you're asking all the right questions. We don't need to solve those today. But now you have some thinking to do and you understand where I want to head this summer with, with all these tools. And so let's do some pre work. You know, start thinking about this. What are they going to challenge is going to be, is it going to be compute? Is it going to be cost? Is it going to be error of hallucinations and reliability and validity? What's the most efficient way to use them? I think there's ways to engineer. You know, one thing I have no shortage of is creativity, you know, being in neuroscience and like reading lots of biology books. I think there's like lots of little cool novel tricks we can do that might be useful in like being more efficient of token usage and things. So like, but let's solve that after we expand this table. So I'm thinking, hey, is like one of the things is you can start thinking about, yes, maybe you and Rohan and, you know, Rohan can point you to the stock market thing. You can start exploring how that might be applicable to what I described. You have my note taker here, so you should get it in your, in your otter. I have to jump. But that, does that make sense?
**Me:** So the current just thinking for today, tomorrow is the trace based embeddings is all good. I started working with other plates, so that'll just continue.
**Them:** Yep.
**Me:** We're going to have benchmark bolts with the data. Bend is going to give or gave. And then we're going to go. Get a bunch of prompts from people to find the limits of emit. And then I'll also send out the email I'll cc you on it for the demo on Tuesday.
**Them:** Yep. Yep. Perfect. Exactly. And then finally time to and schedule the meeting. For us plus Gavin.
**Me:** Schedule for.
**Them:** Tuesday.
**Me:** This.
**Them:** Yeah. For the, the follow-up of the, the table and everything.
**Me:** And then yeah maybe think about sharing the box and also just doing general research as to how we. Could make this work. Yes yes. And then. This is separate I guess after this week after it started expanding the table.
**Them:** Yeah, exactly.
**Me:** Research and we can talk after this about more directed let's yeah I think. Probably have my sorry James weekend I think we're sat now thank you a lot.
**Them:** Yeah. Perfect. All right. Thank. Thank you, guys. It's gonna be a lot. This is gonna be a lot of fun. And I'll share my, I'll share my folder on box now and give it to you. To both of you.
**Me:** James send me the readings that you mentioned as well I'll remind you over teams.
**Them:** Thank you. Okay. Talk to you guys soon.
**Me:** Thank you James. Let's.
