"""Sanity check of the change counts reported by the ASP optimization."""
from pprint import pformat


def repair_count_sanity_check(func, orig_model, repaired_model, repair_counts, logger):
  if isinstance(orig_model, str):
    orig_model = [line for line in orig_model.split('\n') if not line.startswith("%") and not line.isspace()]
  else: assert isinstance(orig_model, list)
  if isinstance(repaired_model, str): repaired_model = repaired_model.split()
  else: assert isinstance(repaired_model, list)
  orig_terms = []
  orig_signs = {}
  for atom in orig_model:
    if atom.startswith("function"):
      f, n = [x.strip() for x in atom.split(')')[0].split('(')[1].split(',')]
      n = int(n)
      if f == func and n > len(orig_terms): orig_terms.extend([set() for _ in range(n - len(orig_terms))])
    elif atom.startswith("regulates"):
      r, f, s = [x.strip() for x in atom.split(')')[0].split('(')[1].split(',')]
      if f == func:
        orig_signs[r] = '+' if s == '0' else '-'
    elif atom.startswith("term"):
      f, t, r = [x.strip() for x in atom.split(')')[0].split('(')[1].split(',')]
      t = int(t)
      if f == func:
        if len(orig_terms) < t: orig_terms.extend([set() for _ in range(t - len(orig_terms))])
        orig_terms[t-1].add(r)

  new_terms = []
  new_signs = {}
  for atom in repaired_model:
    if atom.startswith("node_regulator"):
      t, r = [x.strip() for x in atom.split(')')[0].split('(')[1].split(',')]
      t = int(t)
      if len(new_terms) < t: new_terms.extend([set() for _ in range(t - len(new_terms))])
      new_terms[t-1].add(r)
    elif atom.startswith("activator") or atom.startswith("regulator_activator"):
      r = atom.split(')')[0].split('(')[1].strip()
      assert r not in new_signs
      new_signs[r] = '+'
    elif atom.startswith("inhibitor") or atom.startswith("regulator_inhibitor"):
      r = atom.split(')')[0].split('(')[1].strip()
      assert r not in new_signs
      new_signs[r] = '-'

  orig_regulators = {r for term in orig_terms for r in term}
  new_regulators = {r for term in new_terms for r in term}
  common_regulators = orig_regulators & new_regulators

  if logger:
    logger.debug("Processed functions:"
                  f"\n{orig_regulators = }\n{new_regulators = }\n"
                  f"\n{orig_signs = }\n{new_signs = }\n"
                  f"\n{orig_terms = }\n{new_terms = }")

  n_new_terms = sum(1 for new_term in new_terms if len(new_term) > 0)
  #node id continuity check
  if n_new_terms < len(new_terms): assert len(new_terms) <= len(orig_terms)

  real_counts = {
    "extra-terms" : max(0, n_new_terms - len(orig_terms)),
    "missing-terms" : max(0, len(orig_terms) - n_new_terms),
    "extra-regulators" : len(new_regulators - orig_regulators),
    "missing-regulators" : len(orig_regulators - new_regulators),
    "sign-to-inhibitor" : sum(
      1 for r in common_regulators
      if new_signs[r] == '-' and orig_signs[r] == '+'),
    "sign-to-activator" : sum(
      1 for r in common_regulators
      if new_signs[r] == '+' and orig_signs[r] == '-'),
    "term-extra-regulator" : sum(
      len(new_term - orig_term) for orig_term, new_term  in zip(orig_terms, new_terms)
    ),
    "term-missing-regulator" : sum(
      len(orig_term - new_term) for orig_term, new_term  in zip(orig_terms, new_terms)
      if len(new_term) > 0 # exclude removed nodes
    )
  }
  real_counts["term-number"] = real_counts["extra-terms"] + real_counts["missing-terms"]
  real_counts["regulators"] = real_counts["extra-regulators"] + real_counts["missing-regulators"]
  real_counts["signs"] = real_counts["sign-to-inhibitor"] + real_counts["sign-to-activator"]
  real_counts["term-format"] = real_counts["term-missing-regulator"] + real_counts["term-extra-regulator"]
  real_counts["terms"] = real_counts["term-number"] + real_counts["term-format"]
  if logger:
    logger.debug(f"Changes found:\n{pformat(real_counts)}")

  for crit, count in repair_counts:
    real_c = real_counts.get(crit)
    if real_c is None:
      if logger: logger.warning(f"Could not validate count for criterion {crit}")
    else:
      assert count == real_c, f"Criterion {crit} differs: expected {real_c} got {count}"
  if logger: logger.info("Repair counts are correct")
