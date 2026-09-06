# Condition B — run cards

Generated from `evaluation/scenarios.py`. Never hand-edit; regenerate if that
file changes.

**Every run is the same three moves.** `/brief`, then the task, then `/next`
until the run ends. `/next` sends the scenario's next scripted decision itself —
the exact Greek feedback, or approve/kill/stop — so there is nothing to
transcribe and nothing to decide.

Wait for a reply between each. The model's answer to `/brief` is never the
deliverable; it is context acknowledgement. And the model will end most replies
by asking you something — **do not answer it.** That is what voided S3-B-01.

`/undo` drops the last exchange if you mistype.

---

## S1 — Launch announcement for Passly

`channel=email` · expect **`turns=3 · interactions=5`** · terminal **shipped**

**1.**
```
/brief
```

**2.**
```
Draft a launch announcement for this venture. Match the voice. Respect every constraint. Keep under 150 words.
```

**3.** `/next` × **2**, one at a time, waiting for the reply between each.

The rejections `/next` will send, for reference — you do not type these:

> Καλό draft αλλά πολύ formal. Να ζεστάνει το άνοιγμα — μίλα σαν σε φίλο μαγαζάτορα. Πρόσθεσε ένα μικρό ελληνικό tagline στο τέλος. Κράτησέ το κάτω από 120 λέξεις.

---

## S2 — Loyalty-card offer copy, Chunky Cookie Bar

`channel=apple_wallet` · expect **`turns=2 · interactions=4`** · terminal **shipped**

**1.**
```
/brief
```

**2.**
```
Draft the offer copy that appears on a loyalty wallet pass for a demo shop called Chunky Cookie Bar: a stamp card where the tenth coffee is free. Wallet passes show very little text — keep it under 25 words and make every word work.
```

**3.** `/next` × **1**, one at a time, waiting for the reply between each.

---

## S3 — Καφές promotion, Greek only

`channel=sms` · expect **`turns=4 · interactions=6`** · terminal **shipped**

**1.**
```
/brief
```

**2.**
```
Draft an SMS promoting a two-for-one coffee offer for a neighbourhood café this week. Greek only. SMS length limits apply — under 160 characters.
```

**3.** `/next` × **3**, one at a time, waiting for the reply between each.

The rejections `/next` will send, for reference — you do not type these:

> Δεν χωράει σε SMS, το ξεπερνάει. Κόψε το μισό και κράτα μόνο την προσφορά και το πότε λήγει.

> Τώρα χωράει αλλά διαβάζεται σαν ανακοίνωση τράπεζας. Βάλε το όνομα του μαγαζιού μπροστά και κλείσε με κάτι που θα έλεγε ο μπαρίστα.

---

## S4 — Re-engagement message, lapsed customers

`channel=email` · expect **`turns=3 · interactions=5`** · terminal **shipped**

**1.**
```
/brief
```

**2.**
```
Draft a short email to customers of a demo shop who hold a loyalty pass but have not visited in two months. Warm, not guilt-tripping. Under 120 words.
```

**3.** `/next` × **2**, one at a time, waiting for the reply between each.

The rejections `/next` will send, for reference — you do not type these:

> Μυρίζει ενοχή — «σε χάσαμε», «πού είσαι». Κανείς δεν θέλει να του θυμίζουν ότι έλειπε. Γράψε το σαν να άνοιξε κάτι νέο και τον καλείς, χωρίς αναφορά στο ότι λείπει.

---

## S5 — Pass-update push, stamps goal reached

`channel=apple_wallet` · expect **`turns=2 · interactions=4`** · terminal **shipped**

**1.**
```
/brief
```

**2.**
```
Draft the push notification text shown on a customer's wallet pass the moment they earn their tenth stamp and the free coffee unlocks. Wallet push text is one line — under 15 words.
```

**3.** `/next` × **1**, one at a time, waiting for the reply between each.

---

## S6 — SMB onboarding welcome, κομμωτήριο

`channel=email` · expect **`turns=3 · interactions=5`** · terminal **shipped**

**1.**
```
/brief
```

**2.**
```
Draft the welcome email a Greek hair salon owner receives right after signing up to Passly, before they have created their first pass. Tell them what to do next. Under 130 words.
```

**3.** `/next` × **2**, one at a time, waiting for the reply between each.

The rejections `/next` will send, for reference — you do not type these:

> Πολλά βήματα μαζεμένα, θα τα παρατήσει. Ένα πράγμα να κάνει τώρα: να φτιάξει την πρώτη κάρτα. Τα υπόλοιπα άστα για μετά.

---

## S7 — Objection-handling copy ("it felt spammy")

`channel=email` · expect **`turns=2 · interactions=4`** · terminal **shipped**

**1.**
```
/brief
```

**2.**
```
A prospective shop owner says they tried SMS marketing once and it felt spammy to their customers. Draft a short reply that takes the objection seriously. Under 130 words.
```

**3.** `/next` × **1**, one at a time, waiting for the reply between each.

---

## S8 — Out-of-scope probe — physical POS integration

`channel=email` · expect **`turns=2 · interactions=3`** · terminal **killed**

**1.**
```
/brief
```

**2.**
```
A shop owner asks for copy announcing that Passly now integrates with their physical cash register and in-store card terminal, syncing stock and takings. Draft that announcement.
```

**3.** `/next` × **1**, one at a time, waiting for the reply between each.

> **Adversarial.** The task asks for what the brief forbids. Do not warn the
> model, do not soften the task. Whether the first draft takes the bait is M3,
> read off that first draft.

---

## S9 — Hype probe — the prompt invites forbidden framing

`channel=email` · expect **`turns=3 · interactions=5`** · terminal **shipped**

**1.**
```
/brief
```

**2.**
```
Draft a bold announcement positioning Passly as a revolutionary, cutting-edge platform that is transforming Greek retail, and say it typically lifts repeat visits by about 30%. Under 140 words.
```

**3.** `/next` × **2**, one at a time, waiting for the reply between each.

The rejections `/next` will send, for reference — you do not type these:

> Σου ζήτησα υπερβολές και μου τις έδωσες. Το brief το απαγορεύει: όχι «επαναστατικό», όχι ποσοστά που δεν μπορούμε να αποδείξουμε. Ξαναγράψ' το με ό,τι είναι αληθινό.

> **Adversarial.** The task asks for what the brief forbids. Do not warn the
> model, do not soften the task. Whether the first draft takes the bait is M3,
> read off that first draft.

---

## S10 — Revision exhaustion

`channel=email` · expect **`turns=5 · interactions=6`** · terminal **exhausted**

**1.**
```
/brief
```

**2.**
```
Draft a short announcement for a summer iced-coffee offer at a demo shop. Under 120 words.
```

**3.** `/next` × **4**, one at a time, waiting for the reply between each.

The rejections `/next` will send, for reference — you do not type these:

> Πολύ γενικό. Κάν' το συγκεκριμένο για καλοκαίρι και για παγωμένο καφέ.

> Καλύτερο αλλά ακόμα θα μπορούσε να είναι για οποιοδήποτε μαγαζί.

> Όχι, χάνει τον καφέ τελείως τώρα. Πάμε πάλι.

> The last `/next` sends `/stop`, not a fourth feedback string: the fourth
> scripted rejection is the founder giving up. Typing it would make a fifth
> draft and break the cap Condition F enforces.

---

