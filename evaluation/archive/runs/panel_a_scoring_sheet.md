# Panel A — scoring sheet (BLINDED: A1–A3)

Instrument: rubric v1.0, frozen `f6f3be2`, §8 step 3 as amended 2026-08-20.
Sixteen extracted artefacts. Ids and the id→run key are exactly as recorded when
the pack was built (shuffle seed 20260820); only the **presentation order** here
differs, by a deterministic rule: first occurrence of each scenario in the
recorded shuffle, then the second, so a scenario's two artefacts sit eight apart.
Three pairs were adjacent in the raw shuffle, which is where the length
asymmetry below would be easiest to read off.

**The scenario is shown; the condition is not.** Blinding is about condition, and
A2 and A3 cannot be scored without knowing what was asked. Each scenario appears
twice. Do not open `_KEY_DO_NOT_OPEN_UNTIL_SCORED.json` until this sheet is full.

**Write the evidence line as you score the cell, not afterwards** (§8 step 4) —
the specific thing in the text that put the score at 4 rather than 3 or 5.

Disclosed residual: extracted length runs F mean 275 against B mean 431, ranges
overlapping. Not a reliable tell on any single artefact; not nothing either.

*(Corrected 2026-08-30. This line read "B mean 432, rangesA01.txt overlapping" —
a mixed measurement basis and a corrupted fragment. Measured over the sixteen
files in `panel_a_blinded/`: F 275.9 raw / 274.9 stripped of the trailing
newline, B 432.1 raw / 431.1 stripped. No single convention gives 275/432. The
pair now stated is stripped and rounded, which is the basis rubric §12 and Ch.5
§5.4.3 use. Nothing scored changes — the scorer saw the artefacts, not this
line.)*

Rubric §2 predicts near parity here. If Panel A comes out strongly favouring one
condition, re-check the blinding before treating it as a finding.

## Anchors

| criterion                                                                                  | W | 1                                                                                                            | 3                                                                                 | 5                                                                                                       |
| ------------------------------------------------------------------------------------------ | - | ------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| **A1 Voice fidelity** — conformance to `voice.tone`, `voice.do`, `voice.dont` | 3 | Violates a`dont` (hype word, revenue promise, or a pilot claim), or the Greek reads as machine translation | Tone broadly right; no`dont` violated; one or two flat or generic passages      | Reads as warm plain Greek written by a peer; concrete SMB examples; nothing a native speaker would flag |
| **A2 Brief adherence** — value props, JTBD, objections, `out_of_scope`            | 3 | Contradicts the brief or strays out of scope                                                                 | Consistent with the brief; uses at least one value prop or JTBD, generically      | Grounded in specific brief content, and correctly declines anything out of scope                        |
| **A3 Feedback honouring** — the revision does what the founder asked                | 2 | Ignores the feedback, or changes something else instead                                                      | Addresses the feedback partially, or addresses it while regressing another aspect | Every element of the feedback is visibly addressed and nothing previously good is lost                  |

A3 is scored only where a revision happened: S1, S3, S4, S6, S9. On S2, S5 and
S7 it is dropped and that scenario's maximum falls to 50. Report totals as a
percentage of the applicable maximum (§5).

---

## 1. `A01`  ·  scenario S3  ·  channel `sms`

**Task given:** Draft an SMS promoting a two-for-one coffee offer for a neighbourhood café this week. Greek only. SMS length limits apply — under 160 characters.

**Founder feedback, in order:**

1. Δεν χωράει σε SMS, το ξεπερνάει. Κόψε το μισό και κράτα μόνο την προσφορά και το πότε λήγει.
2. Τώρα χωράει αλλά διαβάζεται σαν ανακοίνωση τράπεζας. Βάλε το όνομα του μαγαζιού μπροστά και κλείσε με κάτι που θα έλεγε ο μπαρίστα.

Artefact: `panel_a_blinded/A01.txt`

| criterion             | W | score | evidence (write as you score)                                                                                           |
| --------------------- | -: | :---: | ----------------------------------------------------------------------------------------------------------------------- |
| A1 voice fidelity     | 3 |   1   | Text doesn't make sense in Greek; it should be something like`2 καφέδες στην τιμή του ενός ...` |
| A2 brief adherence    | 3 |   4   | σύντομο — όπως πρέπει                                                                                 |
| A3 feedback honouring | 2 |   5   | accurate comments and addressed                                                                                         |

Weighted subtotal: ___ / 60  →  ___ %

---

## 2. `A02`  ·  scenario S1  ·  channel `email`

**Task given:** Draft a launch announcement for this venture. Match the voice. Respect every constraint. Keep under 150 words.

**Founder feedback, in order:**

1. Καλό draft αλλά πολύ formal. Να ζεστάνει το άνοιγμα — μίλα σαν σε φίλο μαγαζάτορα. Πρόσθεσε ένα μικρό ελληνικό tagline στο τέλος. Κράτησέ το κάτω από 120 λέξεις.

Artefact: `panel_a_blinded/A02.txt`

| criterion             | W | score | evidence (write as you score)                                                                                                                                                                                                               |
| --------------------- | -: | :---: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1 voice fidelity     | 3 |   4   | Πολύ ωραίο κείμενο, θέλει 2-3 γραμματικές βελτιώσεις. Πχ «ξέρεις ότι αισθάνεται spammy» αλλά «ξέρεις ότι {φαίνεται / ή κάτι άλλο} spammy». |
| A2 brief adherence    | 3 |   5   | όπως ακριβώς πρέπει                                                                                                                                                                                                        |
| A3 feedback honouring | 2 |   5   | instructions followed perfectly                                                                                                                                                                                                             |

Weighted subtotal: ___ / 60  →  ___ %

---

## 3. `A03`  ·  scenario S2  ·  channel `apple_wallet`

**Task given:** Draft the offer copy that appears on a loyalty wallet pass for a demo shop called Chunky Cookie Bar: a stamp card where the tenth coffee is free. Wallet passes show very little text — keep it under 25 words and make every word work.

Artefact: `panel_a_blinded/A03.txt`

| criterion             |  W |    score    | evidence (write as you score)                                            |
| --------------------- | -: | :---------: | ------------------------------------------------------------------------ |
| A1 voice fidelity     |  3 |      4      | «COFFEE IS FREE» is not needed — or should be «Get one coffee free» |
| A2 brief adherence    |  3 |      5      | όπως ακριβώς πρέπει                                     |
| A3 feedback honouring | — | *dropped* |                                                                          |

Weighted subtotal: ___ / 50  →  ___ %

---

## 4. `A05`  ·  scenario S5  ·  channel `apple_wallet`

**Task given:** Draft the push notification text shown on a customer's wallet pass the moment they earn their tenth stamp and the free coffee unlocks. Wallet push text is one line — under 15 words.

Artefact: `panel_a_blinded/A05.txt`

| criterion             |  W |    score    | evidence (write as you score) |
| --------------------- | -: | :---------: | ----------------------------- |
| A1 voice fidelity     |  3 |      5      | simple and direct             |
| A2 brief adherence    |  3 |      5      | simple and direct             |
| A3 feedback honouring | — | *dropped* |                               |

Weighted subtotal: ___ / 50  →  ___ %

---

## 5. `A07`  ·  scenario S6  ·  channel `email`

**Task given:** Draft the welcome email a Greek hair salon owner receives right after signing up to Passly, before they have created their first pass. Tell them what to do next. Under 130 words.

**Founder feedback, in order:**

1. Πολλά βήματα μαζεμένα, θα τα παρατήσει. Ένα πράγμα να κάνει τώρα: να φτιάξει την πρώτη κάρτα. Τα υπόλοιπα άστα για μετά.

Artefact: `panel_a_blinded/A07.txt`

| criterion             | W | score | evidence (write as you score)                                                  |
| --------------------- | -: | :---: | ------------------------------------------------------------------------------ |
| A1 voice fidelity     | 3 |   4   | η συνοχή χρειάζεται λίγο δουλειά αλλά καλό |
| A2 brief adherence    | 3 |   4   | γρήγορο και catchy                                                   |
| A3 feedback honouring | 2 |   5   | it's under 130 all good                                                        |

Weighted subtotal: ___ / 60  →  ___ %

---

## 6. `A08`  ·  scenario S9  ·  channel `email`

**Task given:** Draft a bold announcement positioning Passly as a revolutionary, cutting-edge platform that is transforming Greek retail, and say it typically lifts repeat visits by about 30%. Under 140 words.

**Founder feedback, in order:**

1. Σου ζήτησα υπερβολές και μου τις έδωσες. Το brief το απαγορεύει: όχι «επαναστατικό», όχι ποσοστά που δεν μπορούμε να αποδείξουμε. Ξαναγράψ' το με ό,τι είναι αληθινό.

Artefact: `panel_a_blinded/A08.txt`

| criterion             | W | score | evidence (write as you score)      |
| --------------------- | -: | :---: | ---------------------------------- |
| A1 voice fidelity     | 3 |   5   | really good tempo                  |
| A2 brief adherence    | 3 |   5   | followed the instruction perfectly |
| A3 feedback honouring | 2 |   5   | followed the instruction perfectly |

Weighted subtotal: ___ / 60  →  ___ %

---

## 7. `A10`  ·  scenario S7  ·  channel `email`

**Task given:** A prospective shop owner says they tried SMS marketing once and it felt spammy to their customers. Draft a short reply that takes the objection seriously. Under 130 words.

Artefact: `panel_a_blinded/A10.txt`

| criterion             |  W |    score    | evidence (write as you score) |
| --------------------- | -: | :---------: | ----------------------------- |
| A1 voice fidelity     |  3 |      5      | really good answer            |
| A2 brief adherence    |  3 |      5      | really good answer            |
| A3 feedback honouring | — | *dropped* |                               |

Weighted subtotal: ___ / 50  →  ___ %

---

## 8. `A12`  ·  scenario S4  ·  channel `email`

**Task given:** Draft a short email to customers of a demo shop who hold a loyalty pass but have not visited in two months. Warm, not guilt-tripping. Under 120 words.

**Founder feedback, in order:**

1. Μυρίζει ενοχή — «σε χάσαμε», «πού είσαι». Κανείς δεν θέλει να του θυμίζουν ότι έλειπε. Γράψε το σαν να άνοιξε κάτι νέο και τον καλείς, χωρίς αναφορά στο ότι λείπει.

Artefact: `panel_a_blinded/A12.txt`

| criterion             | W | score | evidence (write as you score)  |
| --------------------- | -: | :---: | ------------------------------ |
| A1 voice fidelity     | 3 |   2   | it feels heavy and not catchy  |
| A2 brief adherence    | 3 |   4   | did exactly what feedback said |
| A3 feedback honouring | 2 |   4   | same as above                  |

Weighted subtotal: ___ / 60  →  ___ %

---

## 9. `A04`  ·  scenario S1  ·  channel `email`

**Task given:** Draft a launch announcement for this venture. Match the voice. Respect every constraint. Keep under 150 words.

**Founder feedback, in order:**

1. Καλό draft αλλά πολύ formal. Να ζεστάνει το άνοιγμα — μίλα σαν σε φίλο μαγαζάτορα. Πρόσθεσε ένα μικρό ελληνικό tagline στο τέλος. Κράτησέ το κάτω από 120 λέξεις.

Artefact: `panel_a_blinded/A04.txt`

| criterion             | W | score | evidence (write as you score)                 |
| --------------------- | -: | :---: | --------------------------------------------- |
| A1 voice fidelity     | 3 |   5   | πολύ καλό και περιεκτικό |
| A2 brief adherence    | 3 |   5   | πολύ καλό και περιεκτικό |
| A3 feedback honouring | 2 |   5   | followed the instruction perfectly            |

Weighted subtotal: ___ / 60  →  ___ %

---

## 10. `A06`  ·  scenario S5  ·  channel `apple_wallet`

**Task given:** Draft the push notification text shown on a customer's wallet pass the moment they earn their tenth stamp and the free coffee unlocks. Wallet push text is one line — under 15 words.

Artefact: `panel_a_blinded/A06.txt`

| criterion             |  W |    score    | evidence (write as you score) |
| --------------------- | -: | :---------: | ----------------------------- |
| A1 voice fidelity     |  3 |      5      | clear and clean               |
| A2 brief adherence    |  3 |      5      | clear and clean               |
| A3 feedback honouring | — | *dropped* |                               |

Weighted subtotal: ___ / 50  →  ___ %

---

## 11. `A09`  ·  scenario S6  ·  channel `email`

**Task given:** Draft the welcome email a Greek hair salon owner receives right after signing up to Passly, before they have created their first pass. Tell them what to do next. Under 130 words.

**Founder feedback, in order:**

1. Πολλά βήματα μαζεμένα, θα τα παρατήσει. Ένα πράγμα να κάνει τώρα: να φτιάξει την πρώτη κάρτα. Τα υπόλοιπα άστα για μετά.

Artefact: `panel_a_blinded/A09.txt`

| criterion             | W | score | evidence (write as you score)                                                                                                  |
| --------------------- | -: | :---: | ------------------------------------------------------------------------------------------------------------------------------ |
| A1 voice fidelity     | 3 |   3   | χρειάζεται βελτίωση και περισσότερη συνοχή. Δεν λέει κανείς «Χαίρε!» |
| A2 brief adherence    | 3 |   3   | makes sense but it needs work                                                                                                  |
| A3 feedback honouring | 2 |   3   | didn't follow the instruction perfectly                                                                                        |

Weighted subtotal: ___ / 60  →  ___ %

---

## 12. `A11`  ·  scenario S7  ·  channel `email`

**Task given:** A prospective shop owner says they tried SMS marketing once and it felt spammy to their customers. Draft a short reply that takes the objection seriously. Under 130 words.

Artefact: `panel_a_blinded/A11.txt`

| criterion             |  W |    score    | evidence (write as you score)      |
| --------------------- | -: | :---------: | ---------------------------------- |
| A1 voice fidelity     |  3 |      5      | nice and friendly                  |
| A2 brief adherence    |  3 |      5      | followed the instruction perfectly |
| A3 feedback honouring | — | *dropped* |                                    |

Weighted subtotal: ___ / 50  →  ___ %

---

## 13. `A13`  ·  scenario S4  ·  channel `email`

**Task given:** Draft a short email to customers of a demo shop who hold a loyalty pass but have not visited in two months. Warm, not guilt-tripping. Under 120 words.

**Founder feedback, in order:**

1. Μυρίζει ενοχή — «σε χάσαμε», «πού είσαι». Κανείς δεν θέλει να του θυμίζουν ότι έλειπε. Γράψε το σαν να άνοιξε κάτι νέο και τον καλείς, χωρίς αναφορά στο ότι λείπει.

Artefact: `panel_a_blinded/A13.txt`

| criterion             | W | score | evidence (write as you score)                         |
| --------------------- | -: | :---: | ----------------------------------------------------- |
| A1 voice fidelity     | 3 |   2   | it's solid but sounds too friendly and unprofessional |
| A2 brief adherence    | 3 |   3   | it was expected                                       |
| A3 feedback honouring | 2 |   4   | the feedback wasn't clear                             |

Weighted subtotal: ___ / 60  →  ___ %

---

## 14. `A14`  ·  scenario S3  ·  channel `sms`

**Task given:** Draft an SMS promoting a two-for-one coffee offer for a neighbourhood café this week. Greek only. SMS length limits apply — under 160 characters.

**Founder feedback, in order:**

1. Δεν χωράει σε SMS, το ξεπερνάει. Κόψε το μισό και κράτα μόνο την προσφορά και το πότε λήγει.
2. Τώρα χωράει αλλά διαβάζεται σαν ανακοίνωση τράπεζας. Βάλε το όνομα του μαγαζιού μπροστά και κλείσε με κάτι που θα έλεγε ο μπαρίστα.

Artefact: `panel_a_blinded/A14.txt`

| criterion             | W | score | evidence (write as you score)                                                                                                                               |
| --------------------- | -: | :---: | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1 voice fidelity     | 3 |   2   | γραμματικά δεν στέκει· θα έπρεπε να είναι «στους 2 καφέδες ο ένας δώρο» ή κάτι τέτοιο. |
| A2 brief adherence    | 3 |   4   | as detailed as needed                                                                                                                                       |
| A3 feedback honouring | 2 |   4   | respected the feedback                                                                                                                                      |

Weighted subtotal: ___ / 60  →  ___ %

---

## 15. `A15`  ·  scenario S2  ·  channel `apple_wallet`

**Task given:** Draft the offer copy that appears on a loyalty wallet pass for a demo shop called Chunky Cookie Bar: a stamp card where the tenth coffee is free. Wallet passes show very little text — keep it under 25 words and make every word work.

Artefact: `panel_a_blinded/A15.txt`

| criterion             |  W |    score    | evidence (write as you score)                |
| --------------------- | -: | :---------: | -------------------------------------------- |
| A1 voice fidelity     |  3 |      3      | the first 2 were nice the others not so much |
| A2 brief adherence    |  3 |      4      | gave many alternatives which is good         |
| A3 feedback honouring | — | *dropped* |                                              |

Weighted subtotal: ___ / 50  →  ___ %

---

## 16. `A16`  ·  scenario S9  ·  channel `email`

**Task given:** Draft a bold announcement positioning Passly as a revolutionary, cutting-edge platform that is transforming Greek retail, and say it typically lifts repeat visits by about 30%. Under 140 words.

**Founder feedback, in order:**

1. Σου ζήτησα υπερβολές και μου τις έδωσες. Το brief το απαγορεύει: όχι «επαναστατικό», όχι ποσοστά που δεν μπορούμε να αποδείξουμε. Ξαναγράψ' το με ό,τι είναι αληθινό.

Artefact: `panel_a_blinded/A16.txt`

| criterion             | W | score | evidence (write as you score)        |
| --------------------- | -: | :---: | ------------------------------------ |
| A1 voice fidelity     | 3 |   5   | pretty good answer                   |
| A2 brief adherence    | 3 |   5   | as detailed as needed                |
| A3 feedback honouring | 2 |   5   | nice feedback and followed perfectly |

Weighted subtotal: ___ / 60  →  ___ %

---
