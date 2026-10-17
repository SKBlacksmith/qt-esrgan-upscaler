# Authors and authorship

## Copyright holder

**Sergey Kuznetsov** (SKBlacksmith) - <https://github.com/SKBlacksmith>

*CrossNetwork* is a name the author uses for his own projects and websites. It
is not a company and not a registered trademark, so it is not used here as a
legal entity or as a claim to any registered right.

## How ESRGAN Batch Upscaler is written

The code in this repository is written and reviewed by large language models.
No human writes or reviews source code here. That is stated openly rather than
hidden, and it applies to the application, the tests, the packaging and the
tooling alike.

The human author contributes the part that directs the work:

- the requirements, the scope and the priorities;
- the architecture and the design decisions, including the split between the
  Qt-free core (`engine.py`), the `QProcess` runner (`runner.py`) and the
  interface (`gui.py`);
- the choice between competing implementations, and the rejection of the ones
  that do not fit;
- the acceptance criteria, and verification of each release on real hardware
  before a tag is cut;
- the curation of the repository: what is committed, what is tagged, and what
  is published.

The code is machine-authored; the selection, arrangement and acceptance of it
are human. Where a jurisdiction asks an applicant to disclose AI-generated
material and describe the human contribution, this file is the record of that
contribution.

## Provenance

Commits and annotated tags from version 0.2.1 onwards are signed with an SSH
key. The signature shows that the commit came from the holder of that key and
was not altered afterwards; it says nothing about copyright, and it needs no
registry, no authority and no third party.

- Signing key fingerprint:
  `SHA256:34LNi3Fmj8Hlc0SJjzUp3sdrUzIvzko2ySeDiemQ4tk`
- Public key: [`keys/miss-v-signing.pub`](keys/miss-v-signing.pub)
- Verifier list: [`keys/allowed_signers`](keys/allowed_signers)

Verification:

```bash
git config gpg.ssh.allowedSignersFile keys/allowed_signers
git verify-tag v0.2.1
git log --show-signature -1
```

## Contributions

The project is published to be used and forked, not to be developed in
collaboration. See [CONTRIBUTING.md](CONTRIBUTING.md) and the Contributions
section of the [README](README.md).

## Contact

Bug reports and questions: GitHub Issues on this repository.
