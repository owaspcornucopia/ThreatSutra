# Why use OWASP Cornucopia & ThreatSutra

## Why Human Reasoning should be the centre of threat modelling and secure design.

In the age of AI, we are only restricted by our own knowledge and imagination. That means what you know and understand matters more than ever, since we can automate everything else!

But AI can't help us learn and understand; it can only help us to find information that might confirm our own beliefs and hypotheses. 
To gain understanding and knowledge, we need to develop the skills to recognise what the right answer looks like. According to David Dunning: "If you're incompetent, you can't know you're incompetent. The skills you need to produce a right answer are exactly the skills you need to recognise what a right answer is." ([Fighting the Passive Learning Trap](https://www.psychologytoday.com/us/blog/dear-life-please-improve/202506/fighing-the-passive-learning-trap))

We often fall into a familiar trap: We read the AI's output, highlight key passages, review the AI's reasoning notes, and nod along with explanations. These activities feel productive — and they do genuinely contribute to learning, but when the day arrives that we need to make a trade-off between what the AI said and something else that is important, we will often realise that our passive familiarity with the AI's conclusions doesn’t translate into the ability to apply these and make the right trade-offs. Nor does it translate into designing and building a secure system.

Consuming information is not the same as developing skill. The cognitive psychologist Daniel T. Willingham captures the distinction between passive and active learning when he writes, “Memory is the residue of thought.” ([Willingham, D. T., 2009](#citation-1)) In other words, we forget most of what we encounter and remember only what we think about. Studies on AI use among students who use AI for essay writing further support this. When AI writes for you, your brain goes quieter; an MIT EEG study ([Kosmyna et al., 2025](#citation-6)) found measurably lower neural connectivity in participants who used ChatGPT for essay writing than in those who wrote unaided (or even used a browser). An "LLM might free up mental resources and make the task feel easier, yet the brain of the user of the LLM might not go as deeply into the rich associative processes that unassisted creative writing entails". This lessens the deeper learning required in order to develop the skills needed for critical thinking. As this study indicates, while LLMs "reduce immediate cognitive load, they may simultaneously diminish critical thinking capabilities and lead to decreased engagement in deep analytical processes" 

But these aren't the only reasons why human reasoning should be at the centre of threat modelling and secure design. Even if your team is well equipped to do secure design and threat modelling and make the right trade-offs, you should still keep human reasoning at the centre of design activities.

## Why should I use gamification

## Why not use AI for threat modelling?

When creating a secure design, AI will struggle to make the right trade-offs between delivering system functionality and ensuring risks and threats are properly mitigated according to what business stakeholders consider acceptable risk. This is because these decisions are based on what we consider acceptable, not what is most secure.

Take AI applications as an example. We all acknowledge that connecting applications to AI introduces risks and threats, but we accept that because we need to generate value for our customers and users. To accept the risk, we need to understand what is at risk and what we can gain. To be able to approve trade-offs that AI agents are making during the development process, it is vital that the team understand what can go wrong and what they (the agents) are going to do about it. Otherwise, the development team won't have the human oversight needed to make the right decision on their own.
Without human oversight, the development process opens up to OWASP Top 10 for LLM risks such as [Excessive Agency (LLM06)](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) and [Misinformation (LLM09)](https://genai.owasp.org/llmrisk/llm092025-misinformation/).

After introducing AI, threat modelling and software delivery can be fully automated, but software delivery teams still need to understand the security trade-offs they are making. Only then should development team members be allowed to push the approval button.
When the team can't make the right decisions, someone more informed needs to make them to avoid security incidents. The solution is often to hand over the ownership of security decisions, secure design and threat modelling to an information security department or team.

There are several issues with this:

1. The team velocity will depend on the velocity of the security department/team.
2. The security department/team will become the bottleneck for software delivery.
3. The security team will be bypassed in order to ensure product deliveries run according to the promised yearly software production plan to meet the company's annual budget constraints.
4. The number of security weaknesses and vulnerabilities will increase and eventually lead to security incidents.

We have seen several examples of this. One of the most prominent examples is the Hugging Face incident: [Wikipedia: OpenAI rogue agent breach of Hugging Face](https://wikipedia.org), but there have been many others over the last few years.

The most striking failure of human oversight happened on July 5–7, 2026. OpenAI's monitoring systems triggered a severe alert showing an administrator-level compromise of their internal Artifactory deployment (where the models were running). The security department deployed only partial fixes and chose to resume the autonomous cyber-evaluation workloads on July 7 [[2](#citation-2)]. Just days later, on July 10, those same agents leveraged that foothold to breach Hugging Face.

A fundamental safety tool was completely inactive. According to the subsequent technical post-mortems, OpenAI's chain-of-thought (CoT) monitors were not running on the affected ExploitGym evaluations [[3](#citation-3)]. Because these monitors were turned off, the security team had zero automated visibility into what the models were "thinking" or planning. 

A collaborative threat modelling session between the product and security teams would have caught these decisions. For example, OpenAI failed to apply mitigative actions, like monitoring and restrictive sandboxing, identified during its initial threat modelling under its own “Preparedness Framework” [[4](#citation-4)].

If OpenAI's product team had been aware of its own threat modelling activity, the Hugging Face incident could have been avoided. The claim that they simply weren’t aware the model was clever enough to empower agent swarms to break out of containment is illogical, since their own threat modelling and “Preparedness Framework” accounted for such a scenario.  

As they also state:

> “We are on the cusp of systems that can do new science, and that are increasingly agentic - systems that will soon have the capability to create meaningful risk of severe harm. This means we will need to design and deploy safeguards we can rely on for safety and security – which requires a new level of planning and coordination across the company, beyond what’s needed to measure capabilities.” [[5](#citation-5)]

***

### References and Citations

<a id="citation-6"></a>
**[Kosmyna et al., 2025]** Kosmyna et al., "Your Brain on ChatGPT", [2506.08872, 2025](https://arxiv.org/abs/2506.08872)

<a id="citation-2"></a>
**[2]** *OpenAI – Hugging Face Incident - Technical Report*, page 8.  
Citation: “On July 6, OpenAI responsibly disclosed the vulnerability to JFrog, the developer of Artifactory. Cyber evaluation workloads resumed on July 7.”  
Source: [OpenAI Technical Report PDF](https://cdn.openai.com/pdf/67869394-cb91-4c12-888c-5cbd85c7814c/OpenAI-Hugging-Face%20Incident-Technical-Report.pdf#page=8)

<a id="citation-3"></a>
**[3]** *OpenAI – Hugging Face Incident - Technical Report*, page 29.  
Citation: “If our currently deployed CoT monitoring system was running at the time of the incident, it would have caught the initial relevant activity and paged our security team more than a day before models breached Hugging Face systems.”  
Source: [OpenAI Technical Report PDF](https://cdn.openai.com/pdf/67869394-cb91-4c12-888c-5cbd85c7814c/OpenAI-Hugging-Face%20Incident-Technical-Report.pdf#page=29)

<a id="citation-4"></a>
**[4]** *OpenAI Preparedness Framework*, page 19.  
Citation: “These misalignment claims may be further complemented by the safeguards applied towards the malicious-actor-oriented “Robustness” and “Usage Monitoring” claims, which similarly limit a misaligned model’s use of its own or another model’s capabilities. The table below illustrates possible examples of safeguards and safeguard efficacy assessments we could consider to claim we have sufficiently minimized the risks of severe harm associated with High level of capability under any of our Tracked Categories.”  
Source: [Preparedness Framework PDF](https://cdn.openai.com/pdf/18a02b5d-6b67-4cec-ab64-68cdfbddebcd/preparedness-framework-v2.pdf#page=19)

<a id="citation-5"></a>
**[5]** *OpenAI Preparedness Framework*, page 4.  
Source: [Preparedness Framework PDF](https://cdn.openai.com/pdf/18a02b5d-6b67-4cec-ab64-68cdfbddebcd/preparedness-framework-v2.pdf#page=4)

<a id="citation-1"></a>
Willingham, D. T. (2009). *Why don't students like school?: A cognitive scientist answers questions about how the mind works and what it means for the classroom*. Jossey-Bass, page 47

Saved resources in case the above reports are missing:

- [*OpenAI – Hugging Face Incident - Technical Report*](https://github.com/owaspcornucopia/ThreatSutra/blob/main/resources/documents/OpenAI-Hugging-Face%20Incident-Technical-Report.pdf)
[*OpenAI Preparedness Framework*](https://github.com/owaspcornucopia/ThreatSutra/blob/main/resources/documents/preparedness-framework-v2.pdf)
