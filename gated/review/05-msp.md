# Gated review: MSP

**6 entries, 4 flagged ⚠️**

Source: `gated/msp.json` (`reviewed: false`). Public one-liners from `src/data/projects.json`. Gated text is shown as the NDA page renders it: summary paragraph, then each section's heading, paragraphs and bullets. Notes are Chris-only and never reach the site.

## 1. AI-powered security hardening for your small business and home (`P-MSP-06`) ⚠️

**Public one-liner:** A new service that finds weak security settings on your computers and home or office network, and helps put them right. Plain English, no jargon.

> ⚠️ **Note in file:** Drafted from the public card and the Resources hardening guides; Chris to confirm scope and timing.

**Gated text:**

> A guided service that checks the security settings on a client's computers and home or office network, explains what it finds in plain English, and helps fix it.
>
> **How it works**
>
> - An AI assistant reviews each device against a hardening checklist built by IT7Q
> - Findings are ranked by risk and explained without jargon
> - Fixes are applied with the client's say-so, then checked again
>
> **Where it's at**
>
> - Checklists for Windows, Android and home routers are being written
> - Pilot with existing managed clients first

## 2. SCUTUM (`P-MSP-01`) ⚠️

**Public one-liner:** 24/7 managed protection for your computers: enterprise-grade, explained in plain English.

> ⚠️ **Claude's note:** Gated text says "target $68 a year per device"; the public card says "From $68 a year (incl. GST)". Pick one wording (target vs from, per device).

**Gated text:**

> Managed protection for Windows computers: Microsoft Defender hardened and tuned as the main shield, backed by IT7Q's own monitoring and an AI-assisted triage step that checks alerts before a person does.
>
> **What clients get**
>
> - Defender configured to a hardened standard, not left on defaults
> - On-demand malware scanning as a second opinion
> - An IT7Q tray icon and a simple protection dashboard on each computer
> - Alerts reach IT7Q's own messaging system (Nexus), so nothing waits in a shared inbox
>
> **Why it's different**
>
> - Alerts are triaged in-house by IT7Q's own AI (Andromeda) first; an outside AI service is used only when genuinely needed, so client data stays with IT7Q
> - Priced for homes and small businesses: target $68 a year per device, including GST
>
> **Where it's at**
>
> - Built for Windows fleets first
> - Being piloted on IT7Q's own monitored devices

## 3. MSP Companion App (`P-MSP-02`) ⚠️

**Public one-liner:** One-click sign-up to IT7Q managed protection.

> ⚠️ **Claude's note:** "IT7Q's existing four-device monitored fleet" reveals how small the fleet is. Fine under NDA, or say "IT7Q's own monitored devices" like SCUTUM does?

**Gated text:**

> A small app that signs a client's device up to IT7Q managed protection in one click, without opening any connection into the client's network.
>
> **Why it matters**
>
> - No inbound access, no router changes, nothing exposed to the internet
> - Takes the fiddly enrolment steps away from the client
>
> **Where it's at**
>
> - Working enrolment service built
> - Pilot on IT7Q's existing four-device monitored fleet

## 4. Managed security monitoring (`P-MSP-03`)

**Public one-liner:** Round-the-clock security monitoring across your computers.

**Gated text:**

> Round-the-clock security monitoring across a client's computers, run on IT7Q's own self-hosted monitoring platform rather than a resold cloud service.
>
> **What it covers**
>
> - Security events collected from Windows, macOS and Linux computers
> - Automatic alerting into IT7Q's automation and messaging systems
> - Plain-English follow-up when something needs doing
>
> **Where it's at**
>
> - Running today on IT7Q's own devices
> - Sign-up guides written per platform; Chromebooks have known limits that are explained up front

## 5. IT7Q Support Portal (`P-MSP-04`)

**Public one-liner:** Your support tickets, devices and help articles in one clean portal.

**Gated text:**

> One place for clients to raise a support ticket, see their devices and read help articles, built in-house so it joins up with the rest of IT7Q's tools.
>
> **Roadmap**
>
> - Stage 1: tickets and devices in a clean app (in progress)
> - Stage 2: a searchable knowledge base and FAQ
> - Stage 3: built into the Athena Browser with single sign-on
> - Stage 4: an AI support layer: automatic first-level triage, escalation, device-aware answers, queue watching and service-level alerts
>
> **Built with**
>
> - A cross-platform app with its own back end and database, all self-hosted

## 6. IT7Q SysMon (`P-MSP-05`) ⚠️

**Public one-liner:** Keeps an eye on server health around the clock and flags problems early.

> ⚠️ **Note in file:** No detail in the build pack. Drafted from the public card; Chris to add features and status.

**Gated text:**

> A server health monitor that watches performance and availability around the clock and raises problems before staff notice them.
>
> **What it watches**
>
> - Uptime, slow-downs and failing services
> - Disk, memory and processor pressure
> - Alerts in plain English, with the likely cause
