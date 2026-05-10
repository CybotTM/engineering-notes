---
title: "How we ended up with a [matrix] based Communication Platform"
slug: "matrix-based-communication-platform"
originally_published: "2020-07"
updated: "2026-05-10"
status: "historical"
topics:
  - platform-engineering
  - communication
  - federated-systems
  - architecture-decisions
summary: "A long-arc decision narrative: from self-hosted XMPP/Prosody (2011) through Skype and Slack to a federated [matrix] platform (2019), and why a small-but-growing engineering organisation ended up choosing an open, federated protocol over SaaS chat."
lang: "en"
license: "CC-BY-4.0"
---

> **Stand: 2020.** This article documents a platform-engineering decision made around 2019–2020. The reasoning still holds up, but surrounding technology has moved on: Matrix/Synapse, Element, the federation model, end-to-end encryption defaults, and the integration ecosystem have all evolved substantially since. Read the decision-narrative for the *why*, not the *how*.
>
> *Disclosure: this was originally written from the perspective of a ~12-person engineering team operating its own infrastructure. Where the original said "we", that team is meant.*

> Matrix (stylized as [matrix]) is an open standard and lightweight protocol for real-time communication.
>
> — <https://en.wikipedia.org/wiki/Matrix_(protocol)>

There is no clear reference before 2011, but it is reasonable to assume that prior to a self-hosted XMPP server — Prosody — the team most likely used some public services like IRC, ICQ or Jabber.org.

## 2011 – 2019: Prosody (XMPP)

At least since 2011 the team ran XMPP-based communication backed by Prosody as the server.

The XMPP server ran on internal infrastructure. Users were automatically provisioned from AD/LDAP — including authentication — and assigned to rooms based on their AD/LDAP groups.

But there were issues. They didn't hurt — for a team of twelve people, instant messaging is more a plus than a requirement. Shortcomings were mitigated by direct contact in real life.

With a growing team and the ever-growing requirement for mobility of team members, these shortcomings started to become annoying.

Acceptance — especially for non-technical and more visually-oriented people — was not as good as it should be. Especially for mobile clients.

People started to avoid the XMPP infrastructure and poisoned the communication landscape by using external services. Communication started to become fragmented, or even lost.

## ? – 2019: Skype

People started to use Skype, which never really was a threat, because of its limited features and lacking Linux support, but it showed friction.

## 2014 – 2020: Slack

In 2014 we started playing around with Slack. Its cross-platform/device web UI was refreshing and gained much better acceptance. Its already existing integrations and interfaces made it a user's choice over XMPP.

But Slack was only available as a service. SaaS pricing for Slack did not fit the requirements, and free features were too limited for the intended use.

For example, at this point in time it entirely lacked any type of video or voice communication ability. Also, being in different teams meant having multiple browser windows or tabs open to stay up to date with all of them. Inviting guests was not possible either without creating accounts. The usability around different accounts and teams is still a mess.

Company values also did not fit very well with Slack — the use of open source software is encouraged wherever applicable.

Sending information around the globe related to customers who sometimes don't even approve of using cloud services seemed disrespectful, too.

The result was communication completely split between XMPP and Slack, due to the missing decision to go with either Slack or XMPP.

## 2019 – Today: [matrix]

In 2016 we started to evaluate other instant messaging systems. The criteria: systems which can (potentially) be integrated with existing or planned services — SaaS or on-premise — such as issue trackers, wikis, source-hosting platforms, monitoring systems, mail, build servers, VOIP/phone, video call, and news sources (security feeds).

Authentication should be based on the central user-management service, and native mobile and desktop clients should be available, as well as a web client.

It should be able to add/invite guests or connect with foreign instances of the same software or service type.

Based on these requirements, we started to evaluate software such as Rocket.Chat, [matrix], Jitsi, Slack, and FreePBX. It took us 3 years before we came to a decision — sounds like a long time, but because we started early, before problems with current communication could become a real threat, there was no pressure: it was no main project, nor always in complete focus.

Finally in 2019, the XMPP service was dropped in favor of [matrix], and the Slack team was abandoned.

## No regrets

So far there have been no major complaints from any involved party — but maybe this is going to change with publishing this article. We'll see.

As part of the [matrix] federation network, which our server joined, it is possible to invite guests from foreign [matrix] servers (company or public ones) to join rooms on our server. And of course, colleagues are able to join foreign public rooms on other servers.

Setting up all the service components — the server itself, the web client, database, auth integrations, etc. — was just as easy as a `git clone` and an Ansible run. Thanks to <https://github.com/spantaleev/matrix-docker-ansible-deploy>.

Some services are already integrated, mainly notifications from monitoring, build servers and the ticket system. There is also the possibility to easily bridge to different networks such as Telegram, Facebook, IRC or Slack.

There is still a lot of room for further improvements regarding integration of our services, but thanks to a very active and open ecosystem around [matrix], the future here looks bright.

## References

- Team Chat / Communication (outlook)
- XMPP (Jabber) Administration
- Neue Kommunikationsplattform / new Communication platform
- [Matrix](https://matrix.org/)
- Matrix client (Riot, now [Element](https://element.io/))
- Webhooks for the win
- GitLab notifications with [maubot](https://github.com/maubot/maubot)
- Notifications utilization general-purpose webhook

---

*Originally published as an internal Netresearch wiki article in July 2020. Republished here as a historical record of the decision; surrounding technology has evolved since.*
