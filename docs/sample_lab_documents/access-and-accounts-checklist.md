# Access, Accounts, and Permissions Checklist

This checklist covers everything a new lab member needs to request before they
can do hands-on work. Most items take 1–5 business days to provision, so start
on day one. Owner: Sara Kowalski (kowalski@example.lab).

## Physical access

| Access | Approver | How to request | Typical turnaround |
|--------|----------|----------------|-------------------|
| Building badge | Facilities (Sasha Reid) | Submit the new-hire form on the institution intranet | 2–3 business days |
| Lab door PIN | Sara Kowalski | Slack DM with start date and full name | Same day |
| Tissue culture room key card | Marcus Cho | Email request, copies Daniel Okafor | 2 business days |
| Cold room key | Yuki Tanaka | Pickup in person; sign log | Same day |
| Hood / fume hood air handler badge | Daniel Okafor | After safety training is signed off | After training only |

## Software accounts

| Account | Approver | What it's for |
|---------|----------|---------------|
| Lab GitHub org (`lab-org`) | Hannah Liu | Source code, analyses, infrastructure |
| Benchling | Sara Kowalski | Lab notebook entries, sample tracking |
| Slack workspace | Auto-provisioned via SSO | All lab communication |
| Google Workspace lab folder | Auto-provisioned via SSO | Manuscripts, shared drives |
| `lab-storage` SSH access | Hannah Liu | Mount raw and processed data shares |
| Zeiss imaging cloud | Priya Mehta | Confocal data review and export |
| Equipment booking calendars (microscopes, plate reader, hoods) | Yuki Tanaka | Calendar invites + permissions |

## What to do before your first hands-on day

1. Submit the building badge request the day you accept the offer if
   possible — this is the longest turnaround.
2. Schedule your safety walk-through with Daniel Okafor for week one. You
   cannot get hood access without it.
3. Book a 30-minute "tour and introductions" with Sara Kowalski. She'll
   walk you through the physical lab, point out the safety stations, and
   flag any access requests still in flight.
4. Ask your project lead which equipment owners you should meet first and
   which calendars you need access to.

## Verify access before your first run

The day before any planned experiment, verify that:

- Your badge actually opens the lab door and the relevant rooms.
- You can log into Benchling and see the lab project workspace.
- You can mount `/lab-storage` from the workstation you'll use.
- The equipment calendar shows you as a "can edit" user (not just viewer).

If any of those fail, ping Sara Kowalski in `#lab-general`. Showing up to a
booked microscope slot without working access is the most common avoidable
delay we see.
