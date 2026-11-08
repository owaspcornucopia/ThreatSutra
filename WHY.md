# Why use games like OWASP Cornucopia together with ThreatSutra

In the age of AI, we are only restricted by our own understanding and imagination. What you know and understand matters more than ever, as we can automate everything else. Our understanding and imagination will set the limits of what we can achieve: if we can't understand or imagine it, we can't achieve it.
We need imaginationmaxxing, not tokenmaxxing. By combining gamification with AI automation, we can maximise the acquisition of complex skills through playful work designs made to increase cognition and the capacity for innovation, without interrupting the process with repetitive tasks like typing on a keyboard or copy-pasting text. ThreatSutra aims to create a seamless experience where threat elicitation, through gamification, is magically turned into work items and drawings that support the development process while ensuring the team understands how to make the right trade-offs between delivering system functionality and properly mitigating risks and threats. 

## Why Human Reasoning should be at the centre of threat modelling and secure design.

AI can't help us learn and understand; it can only help us to find information that might confirm our own beliefs and hypotheses. 
To gain understanding and knowledge, we need to develop the skills to recognise what the right answer looks like. According to David Dunning: "If you're incompetent, you can't know you're incompetent. The skills you need to produce a right answer are exactly the skills you need to recognise what a right answer is." ([Fighting the Passive Learning Trap](https://www.psychologytoday.com/us/blog/dear-life-please-improve/202506/fighing-the-passive-learning-trap))

We often fall into a familiar trap of reading the AI's output, highlighting key passages, reviewing the AI's reasoning notes, and nodding along with the explanations. These activities feel productive — and they do genuinely contribute to learning, but when we need to make a trade-off between what the AI said and something someone else said was important, we will often realise that our passive familiarity with the AI's conclusions doesn’t translate into the ability to apply these and make the right trade-offs when confronted in a team meeting by our colleagues or our superiors. Nor does it translate into understanding what it takes in order to design and build a secure system.

Consuming information is not the same as developing skill. The cognitive psychologist Daniel T. Willingham captures the distinction between passive and active learning when he writes, “Memory is the residue of thought.” ([Willingham, D. T., 2009](#citation-1)) In other words, we forget most of what we encounter and remember only what we think about. Studies on AI use among students who use AI for essay writing further support this. When AI writes for you, your brain goes quieter; an MIT EEG study ([Kosmyna et al., 2025](#citation-6)) found measurably lower neural connectivity in participants who used ChatGPT for essay writing than in those who wrote unaided (or even used a browser). An "LLM might free up mental resources and make the task feel easier, yet the brain of the user of the LLM might not go as deeply into the rich associative processes that unassisted creative writing entails". This lessens the deeper learning required to develop the skills needed for critical thinking. As this study indicates, while LLMs "reduce immediate cognitive load, they may simultaneously diminish critical thinking capabilities and lead to decreased engagement in deep analytical processes".
Neuroscience research suggests a sweet spot for difficulty. Research suggests the optimal challenge level for learning is around an 85% success rate. That is hard enough to build capacity, but not so hard your brain shuts down. AI typically pushes users toward 100% effortless success, which skips the zone where learning happens ([Oakley et al., 2025](#citation-7)). 

But these aren't the only reasons why human reasoning should be at the centre of threat modelling and secure design. Even if your team is well equipped to do secure design and threat modelling and make the right trade-offs, you should still keep human reasoning at the centre of design activities.

## Why not use AI to completely automate threat modelling?

When creating a secure design, AI will struggle to make the right trade-offs between delivering system functionality and ensuring risks and threats are properly mitigated according to what business stakeholders consider acceptable risk. This is because these decisions are based on what we consider acceptable, not what is most secure.

Take AI applications as an example. We all acknowledge that connecting applications to AI introduces risks and threats, but we accept that because we need to generate value for our customers and users. To accept the risk, we need to understand what is at risk and what we can gain. To be able to approve trade-offs that AI agents are making during the development process, it is vital that the team understand what can go wrong and what they (the agents) are going to do about it. Otherwise, the development team won't have the human oversight needed to make the right decision on their own.
Without human oversight, the development process opens up to OWASP Top 10 for LLM risks such as [Excessive Agency (LLM06)](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) and [Misinformation (LLM09)](https://genai.owasp.org/llmrisk/llm092025-misinformation/).

After introducing AI, threat modelling and software delivery can be fully automated, but software delivery teams still need to understand the security trade-offs they are making. Only then should development team members be allowed to push the approval button.
When the team can't make the right decisions, someone more informed needs to make them to avoid security incidents. The solution is often to hand over the ownership of security decisions, secure design and threat modelling to an information security department or team.

There are several issues with this:

1. The team velocity will depend on the velocity of the security department/team.
2. The security department/team will become the bottleneck for software delivery.
3. The security team will be bypassed in order to ensure product deliveries run according to the promised yearly software production plan to meet the company's annual budget constraints.
4. The number of security weaknesses and vulnerabilities will increase due to the lack of human oversight and will eventually lead to security incidents.

We have seen several examples of this. One of the most prominent examples is the Hugging Face incident: [Wikipedia: OpenAI rogue agent breach of Hugging Face](https://wikipedia.org), but there have been many others in recent years.

The most striking failure of human oversight happened on July 5–7, 2026. OpenAI's monitoring systems triggered a severe alert showing an administrator-level compromise of their internal Artifactory deployment (where the models were running). The security department deployed only partial fixes and chose to resume the autonomous cyber-evaluation workloads on July 7 [[1](#citation-2)]. Just days later, on July 10, those same agents leveraged that foothold to breach Hugging Face.

A fundamental safety tool was completely inactive. According to the subsequent technical post-mortems, OpenAI's chain-of-thought (CoT) monitors were not running on the affected ExploitGym evaluations [[2](#citation-3)]. Because these monitors were turned off, the security team had zero automated visibility into what the models were "thinking" or planning. 

A collaborative threat modelling session between the product and security teams would have caught these decisions. For example, OpenAI failed to apply mitigative actions, like monitoring and restrictive sandboxing, identified during its initial threat modelling under its own “Preparedness Framework” [[3](#citation-4)].

If OpenAI's product team had been aware of its own threat-modelling activity, it could have avoided the Hugging Face incident. The claim that they simply weren’t aware the model was clever enough to empower agent swarms to break out of containment is insufficient for explaining why the incident happened, since their own threat modelling and “Preparedness Framework” accounted for such a scenario.

As they also state:

> “We are on the cusp of systems that can do new science, and that are increasingly agentic - systems that will soon have the capability to create meaningful risk of severe harm. This means we will need to design and deploy safeguards we can rely on for safety and security – which requires a new level of planning and coordination across the company, beyond what’s needed to measure capabilities.” ([OpenAI, 2025, page 190](#citation-5))

## Why we should play games

The brain is amazing. It can help you learn to ride a bike, write poetry, learn a new programming language, or even fall in love, but if your brain is so amazing, why do your colleagues forget everything you said during your last meeting?
Games can foster agency, empathy, community, imagination, and brain stimulation. When choosing a strategy to make your applications more secure, don’t choose reading materials, presentations with “talking heads,” or meetings to increase awareness and knowledge of application security. Instead, focus on activities you can repeat regularly that are both relevant and engaging to the work you do. When employees are genuinely involved and curious about their learning, their heightened focus and emotional connection lead to better memory formation and knowledge application. Numerous studies show that emotions significantly affect human cognitive processes. This helps explain why games can enhance learning over time, and why having an extensive collection of games in your arsenal benefits teaching others about security.
Playfulness facilitates learning (Chughtai, 2020; Petelczyc et al., 2018; Spraggon & Bodolica, 2018) by creating a unique learning environment, a ‘playspace’ where individuals can experiment with new ideas and challenge existing assumptions (Kinder et al., 2018). In his ethnographic research, Chughtai (2020) found that IT professionals’ playfulness related to gradually acquiring complex skills: employees learned IT-related skills by playing with their work and then mastered them as if progressing through levels in a game. Despite this, people mostly see gameplay as a diversion that takes them out of the work context. This is because culture and society commonly associate it with what is called "Diversionary play". Diversionary play is a form of play meant to disengage from work tasks and serve as a break from work; it can include enjoyable, non-work-related activities such as humour and playful conversations in the break room or performing leisure
activities, such as playing games or daydreaming, during the workday (Mainemelis & Ronson, 2006). In contrast, work-embedded play integrates playfulness into work
tasks, enhancing creativity and innovation through approaches such as playful brainstorming or problem-solving (Mainemelis & Ronson, 2006), but work-embedded play can also often become overly facilitated, mandatory, or serious. When playfulness is removed from serious game activity, it risks losing its intrinsic value and restricting engagement by placing too much emphasis on outcomes (Proyer, 2012; Sicart, 2014). Therefore, it's important to keep the informal, fun, and playful aspects during work-embedded play, such as when playing "serious games" like OWASP Cornucopia, EoP or Cumulus. Despite these benefits, a common assumption is that play activities are inefficient and steal time from work activities, but several reports point to playfulness being positively related to
performance at work (Bakker et al., 2021; Bakker, Hetland, et al., 2020; Caracuzzo et al., 2024; Dishon-Berkovits et al., 2023; Liu et al., 2024). When playfulness is integrated into daily work tasks—known in organisational literature as Playful Work Design (PWD) —it supports work performance through work engagement (Caracuzzo et al., 2024; Dishon-Berkovits et al., 2023). When individuals engage in play, they become fully absorbed, committed to continuing, and often do so with great energy, leading to increased performance (Dishon-Berkovits et al., 2023; Liu et al., 2024)

### To Conclude

Research on the use of playfulness and gamification in the workplace, and their impact on human cognition and threat modelling, is, without a doubt, both emerging and uncertain. We know little about the impact games have on the workplace, and even less about the impact AI has on human cognition, but enough circumstantial evidence exists to form a conjecture about a more beneficial path for facilitating threat modelling in secure design. 
On the one hand, it is clear that human reasoning needs to be at the centre. Without proper human oversight, we will not know what our AI agents are up to. We must understand the threats and risks involved and how to mitigate them to make the right trade-offs between delivering system functionality and properly mitigating risks and threats. That said, AI agents can find exploits, write code, and do a range of other activities, including threat elicitation and requirement analysis. As more development and operational activities become AI-driven, threat modelling and secure design must keep up with the pace. I believe we can do this by combining gamification with AI automation to maximise the acquisition of complex skills through playful work designs that increase cognition and the capacity for innovation. The alternative would be to give in to the machine and hope for the best or turn off our computer. I don't think either is a viable alternative.
As a threat model practitioner, I believe in the values put forth by the threat modelling manifesto. 

We have come to value:

- A culture of finding and fixing design issues over checkbox compliance.
- People and collaboration over processes, methodologies, and tools.
- A journey of understanding over a security or privacy snapshot.
- Doing threat modeling over talking about it.
- Continuous refinement over a single delivery.

That is, while the items on the right have value, we value the items on the left more.

### Quotes

<a id="citation-2"></a>
**[1]**: “On July 6, OpenAI responsibly disclosed the vulnerability to JFrog, the developer of Artifactory. Cyber evaluation workloads resumed on July 7.” (OpenAI, 2026, page 8)

<a id="citation-3"></a>
**[2]**: “If our currently deployed CoT monitoring system was running at the time of the incident, it would have caught the initial relevant activity and paged our security team more than a day before models breached Hugging Face systems.” (OpenAI, 2026, page 29)

<a id="citation-4"></a>
**[3]**: “These misalignment claims may be further complemented by the safeguards applied towards the malicious-actor-oriented “Robustness” and “Usage Monitoring” claims, which similarly limit a misaligned model’s use of its own or another model’s capabilities. The table below illustrates possible examples of safeguards and safeguard efficacy assessments we could consider to claim we have sufficiently minimized the risks of severe harm associated with High level of capability under any of our Tracked Categories.” ([OpenAI, 2025, page 190](#citation-5))

### References and Citations

Bakker, A. B., Breevaart, K., Scharp, Y., & de Vries, J. (2021). Daily self-leadership and playful work design: Proactive approaches of work in times of crisis. The Journal of Applied Behavioral Science, 59(2), 314–336. https://doi.org/10.1177/00218863211060453

Bakker, A. B., Hetland, J., Olsen, O. K., Espevik, R., & de Vries, J. D. (2020). Job crafting and playful work design: Links with performance during busy and quiet days. Journal of Vocational Behavior, 122, 103478. https://doi.org/10.1016/J.JVB.2020.103478

Caracuzzo, E., Caputo, A., Callea, A., Cortese, C. G., & Urbini, F. (2024). Playful work design in fostering organizational citizenship behaviors and performance: two studies on the mediating role of work engagement. Management Research Review, 47(9), 1422–1440. https://doi.org/10.1108/MRR-05-2023-0354

Chughtai, H. (2020). Instrumental aspects of play at work in information technology organisations. European Journal of Information Systems, 30(6), 659–675. https://doi.org/10.1080/0960085X.2020.1854061

Dishon-Berkovits, M., Bakker, A. B., & Peters, P. (2023). Playful work design, engagement and performance: the moderating roles of boredom and conscientiousness. The International Journal of Human Resource Management, 35(2), 256–283. https://doi.org/10.1080/09585192.2023.2227920

Kinder, T., Stenvall, J., & Memon, A. (2018). Play at work, learning and innovation. Public Management Review, 21(3), 376–399. https://doi.org/10.1080/14719037.2018.1487578

<a id="citation-6"></a>
Kosmyna, N., Hauptmann, E., Yuan, T. Y., Situ, J., Liao, X.-H., Beresnitzky, A. V., Braunstein, I., Maes, P. (2025). Your Brain on ChatGPT: Accumulation of Cognitive Debt when Using an AI Assistant for Essay Writing Task, arXiv preprint, 10.48550/arXiv.2506.08872

Liu, Z., Yuan, L., Cao, C., Yang, Y., & Zhuo, F. (2024). How playfulness climate promotes the performance of millennial employees – the mediating role of change self-efficacy. Journal of Organizational Change Management, 37(3), 603–618. https://doi.org/10.1108/JOCM-08-2023-0344

Mainemelis, C., & Ronson, S. (2006). Ideas are Born in Fields of Play: Towards a Theory of Play and Creativity in Organizational Settings. Research in organizational behavior, 27, 81–131. https://doi.org/10.1016/S0191-3085(06)27003-5

<a id="citation-7"></a>
Oakley, B., Johnston, M., Chen, K.-Z., Jung, E., & Sejnowski, T. (2025). “The Memory Paradox:
Why Our Brains Need Knowledge in an Age of AI.” In The Artificial Intelligence Revolution:
Challenges and Opportunities (Springer Nature, forthcoming), arXiv preprint, https://arxiv.org/abs/2506.11015

OpenAI. (2026). OpenAI – Hugging Face Incident: Technical Report, https://cdn.openai.com/pdf/67869394-cb91-4c12-888c-5cbd85c7814c/OpenAI-Hugging-Face%20Incident-Technical-Report.pdf

<a id="citation-5"></a>
OpenAI. (2025). Preparedness Framework, version 2, https://cdn.openai.com/pdf/18a02b5d-6b67-4cec-ab64-68cdfbddebcd/preparedness-framework-v2.pdf

Petelczyc, C. A., Capezio, A., Wang, L., Restubog, S. L. D., & Aquino, K. (2018). Play at Work: An Integrative Review and Agenda for Future Research. Journal of Management, 44(1), 161–190. https://doi.org/10.1177/0149206317731519

Proyer, R. (2012). Development and initial assessment of a short measure for adult playfulness: The SMAP. Personality and Individual Differences, 53(8), 989–994. https://doi.org/10.1016/J.PAID.2012.07.018

Sicart, M. (2014). Play matters. MIT Press. https://doi.org/10.7551/mitpress/10042.001.0001

Spraggon, M., & Bodolica, V. (2018). A practice-based framework for understanding (informal) play as practice phenomena in organizations. Journal of Management & Organization, 24(6), 846–869. https://doi.org/10.1017/jmo.2018.30

<a id="citation-1"></a>
Willingham, D. T. (2009). *Why don't students like school?: A cognitive scientist answers questions about how the mind works and what it means for the classroom*. Jossey-Bass, page 47

Saved resources in case the above reports are missing:

- [*OpenAI – Hugging Face Incident - Technical Report*](https://github.com/owaspcornucopia/ThreatSutra/blob/main/resources/documents/OpenAI-Hugging-Face%20Incident-Technical-Report.pdf)
- [*OpenAI Preparedness Framework*](https://github.com/owaspcornucopia/ThreatSutra/blob/main/resources/documents/preparedness-framework-v2.pdf)
- [Why don't students like school?](https://github.com/owaspcornucopia/ThreatSutra/blob/main/resources/documents/Daniel%20T.%20Willingham%20Why-dont-students-like-school.pdf)
