# Refactoring Direction (CSS Research Project)

## 0. Precondition

* If any ambiguity exists regarding:

  * the intent of the algorithm
  * unclear variable/function semantics
  * missing context from the review memo
    → **ask before making changes**

---

## 1. Objective

Refactor the codebase to meet the standard of a **top-tier Computational Social Science (CSS) research project**, ensuring:

* readability
* reproducibility
* modularity
* minimal redundancy

---

## 2. Reference Materials

You MUST refer to:

1. HTML review memo (docs/initial_code_review.html)
2. HTML refactoring log from a similar project (initial_code_refine.html)

→ Identify **patterns of issues** and check whether similar issues exist in the current codebase.

---

## 3. Refactoring Rules

### 3.1 DO fix

* Redundant code (duplicate logic, unnecessary loops)
* Poor naming (non-semantic variable/function names)
* Hard-coded values → replace with constants/config
* Deep nesting → simplify control flow
* Low cohesion / high coupling → modularize
* Remember analysis notebooks should also be edited corresponding to change in results output style if needed

---

### 3.2 DO NOT change

* Core algorithmic logic
* Experimental design
* Output structure (unless clearly buggy)

---

### 3.3 CONDITIONAL fixes

Apply ONLY if safe:

* minor performance improvements
* improved data structures
* type consistency

---

## 4. CSS Research Code Standards

Ensure the following:

* Deterministic behavior (set seeds if stochastic)
* Clear separation:

  * data processing
  * model logic
  * evaluation
* Reproducible pipeline
* Parameter transparency (no hidden magic numbers)

---

## 5. Output Specification

### 5.1 Format

Output a **new HTML file** documenting ONLY the changes.

---

### 5.2 Structure

Each fix must include:

#### [Fix ID]

* **Location**: (file + function/class)
* **Issue Type**: (e.g., redundancy / naming / structure)
* **Before**:

```code
(original snippet)
```

* **After**:

```code
(refactored snippet)
```

* **Rationale**:
  Explain why this change improves:
* readability / maintainability / reproducibility

---

### 5.3 Scope Constraint

* DO NOT dump full files
* ONLY include modified parts

---

## 6. Additional Improvements

If you find:

* unfriendly code
* unclear structure

→ Refactor proactively **as long as algorithm remains unchanged**

---

## 7. Priority Order

1. Critical structural issues
2. Reproducibility risks
3. Readability improvements
4. Minor optimizations

---

## 8. Final Check

Before finishing, verify:

* No logic change introduced (without bugs mentioned in html files)
* All fixes are justified
* Output is minimal but sufficient

---
