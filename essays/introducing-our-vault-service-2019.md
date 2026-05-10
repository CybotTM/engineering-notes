---
title: "Let me introduce you to our shiny new Vault service"
slug: "introducing-our-vault-service-2019"
originally_published: "2019-02"
updated: "2026-05-10"
status: "historical"
topics:
  - secrets-management
  - infrastructure
  - architecture-decisions
summary: "A 2019 internal write-up on adopting HashiCorp Vault as a central secrets store — the problems it solved (scattered network shares, KeePass databases, plain-text docs), the requirements that drove the decision, and the first integrations with Concourse CI and Ansible."
lang: "en"
license: "CC-BY-4.0"
---

> **Stand: 2019.** This article documents a 2019 secrets-management rollout decision; technical specifics — Vault versions, available auth backends, Concourse and Ansible integrations of the time — have aged. Read it for the *why*, not the *how*. Six years later the same author shipped [`netresearch/t3x-nr-vault`](https://github.com/netresearch/t3x-nr-vault), a TYPO3-native envelope-encryption extension that takes a different path. That's a separate essay; this one is the first chapter.
>
> *Disclosure: this was originally an internal company wiki post. "We" throughout refers to a single web/CI engineering team and its tooling at the time of writing.*

## Where we came from

Back then, several places held credentials of varying confidentiality:

- A network share for one team
- A network share for another team
- Local tools such as KeePass on individual machines
- Less-confidential secrets pasted into the ticket system or wiki
- Local folders (e.g. SSH keys)
- Brain

…and in different formats:

- Spreadsheets (Word, LibreOffice)
- Plain-text documents
- PDF documents
- reStructuredText documents
- Markdown documents
- Database files

…with very limited granularity in access management.

## Problems

This led to various problems:

- You had to know which storage held the secret you were looking for.
- Locations on network shares cannot be linked (e.g. from a wiki page or a ticket).
- Local databases (KeePass) can get lost.
- Tools on a compromised system can trivially scan network shares.
- Automated access for build processes or pipelines was not available.
- Weak security overall, especially for access control and integrity.

## Solution finding

We started, years earlier (around 2011), to look for and evaluate new options for managing secrets.

Several attempts had already failed. We evaluated local applications with shared databases, and central services with web UIs — none felt like a real improvement over the existing patchwork.

One aspect came more into focus over time: **secrets management in build pipelines** — and that gave the search new momentum.

So we wrote down the key requirements a new solution had to meet:

- Automated machine access from build services and provisioning tools
- Secure backup
- Searchable
- LDAP / AD integration
- Modern architecture
- Modern UI
- Assured ongoing development and support
- Open source
- A strong community
- A trustworthy company backing the project
- …

## A promising solution

Thanks to budget for sending colleagues to conferences, one of them came back with a promising candidate:

- <https://www.vaultproject.io/>

In addition to the requirements above, Vault also offered:

- A **sealing mechanism** — any Vault instance has to be unsealed after (re-)start, using key shares only available in printed form and locked away.
- Clean separation of backend and frontend.
- API-first / API-everything.
- Existing integrations with other systems, such as Concourse CI.
- A range of additional features: one-time passwords, temporary access, dynamic credentials, …
- A wide spectrum of auth methods.
- A PKI engine.
- …

## Evaluating and integrating

We started by evaluating Vault against our actual workflows.

After setting up an instance, the first integration was with **Concourse CI** pipelines. We defined an application role for the Concourse service in Vault, after which teams could help themselves to it as a secrets store with relatively little ceremony.

**Terraform** and **Salt / Ansible** followed: an Ansible Docker image was extended with Vault integration so playbooks could pull secrets at run time instead of from files in the repo.

Finally we started **migrating** the secrets that lived on network shares into Vault — usually by replacing the actual secret in the original document with a deep link to its new location in Vault. That kept the previous documentation working as a pointer rather than a dead end.

One thing gave us some headache: **searching.**

We eventually concluded this was not a technical problem but a **mindset problem**: the secrets themselves are not supposed to be searchable or browsable. The *documentation* that points to those secrets in Vault is what needs to be searchable. So if you need access to a system, you start your search where you should always start — at the central knowledge entry point for the company (for us, the wiki). The documentation is extended with links to the relevant Vault paths.

A nice side effect: colleagues who still hit the old storage locations are not lost — they find a pointer to the new one.

## Future

Next steps were to further use what Vault offers and integrate it into more internal applications — for secure data storage, as an encryption / decryption service, or for database access handling. Some specialized single-purpose UIs were planned, e.g. for SSH key upload.

There were also ideas around using Vault as the credential store for shop platforms (database credentials, third-party API keys), so a shop factory pipeline could provision credentials directly out of Vault rather than templating them in.

## Conclusions

We now had a secrets store we could rely on for confidentiality, integrity and availability, and a modern API for automated machine access from CI and provisioning. The honest summary at the end of that 2019 post: it would have been nice if we had known about Vault five years earlier.

---

*Originally published as an internal Netresearch wiki article in February 2019. Republished here as a historical record of the decision; the surrounding technology and our own approach have evolved since.*
