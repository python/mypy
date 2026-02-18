# Report for assignment 3

This is a template for your report. You are free to modify it as needed.
It is not required to use markdown for your report either, but the report
has to be delivered in a standard, cross-platform format.

## Project

Name:

URL:

One or two sentences describing it

## Onboarding experience

Did it build and run as documented?

See the assignment for details; if everything works out of the box,
there is no need to write much here. If the first project(s) you picked
ended up being unsuitable, you can describe the "onboarding experience"
for each project, along with reason(s) why you changed to a different one.


## Complexity

1. What are your results for five complex functions?
   * Did all methods (tools vs. manual count) get the same result?
   * Are the results clear?
2. Are the functions just complex, or also long?
3. What is the purpose of the functions?
4. Are exceptions taken into account in the given measurements?
5. Is the documentation clear w.r.t. all the possible outcomes?

### `solve_constraints@mypy/solve.py`
Lizard's output for `solve_constraints` in `mypy/solve.py` is as follows:
```
  NLOC    CCN   token  PARAM  length  location
------------------------------------------------
    57     30     423      5      86  solve_constraints@41-126@mypy/solve.py
```

By manually counting the number of `if`, `for` and `else` statements we got a CC of **18**, not matching the 30 reported by Lizard. The difference lies in logical clauses and list comprehensions, which were initially overlooked.

With counting each logical clause (e.g., `and`, `or`) as well as the `for` and `if` statements inside of comprehensions, we arrive at a CC of **30**, matching Lizard's output.

This function in particular is just complex, but not aggressively long. Although 57 lines of code is at the upper end of what should be considered acceptable. Further this function in particular clearly has a lot of different responsibilities (handling three separate boolean flags), which could be a sign that it is possible to reduce its complexity by refactoring those out as separate handlers.

The purpose of the function in to solve type constraints for type variables in the checked program. Which is a core part of the type checking process.

There are no exceptions raised in this function, so they are not taken into account.

The documentation for the function is not very clear. The code is somewhat descriptive but lacks a lot of comments given its complexity and the docstring only gives a very high-level overview. I also feel that the naming of a lot of stuff may be a little to generic, there is a lot of `solve_x`.

## Refactoring

Plan for refactoring complex code:

Estimated impact of refactoring (lower CC, but other drawbacks?).

Carried out refactoring (optional, P+):

git diff ...

## Coverage

### Tools

Document your experience in using a "new"/different coverage tool.

How well was the tool documented? Was it possible/easy/difficult to
integrate it with your build environment?

### Your own coverage tool

Show a patch (or link to a branch) that shows the instrumented code to
gather coverage measurements.

The patch is probably too long to be copied here, so please add
the git command that is used to obtain the patch instead:

git diff ...

What kinds of constructs does your tool support, and how accurate is
its output?

### Evaluation

1. How detailed is your coverage measurement?

2. What are the limitations of your own tool?

3. Are the results of your tool consistent with existing coverage tools?

## Coverage improvement

Show the comments that describe the requirements for the coverage.

Report of old coverage: [link]

Report of new coverage: [link]

Test cases added:

git diff ...

Number of test cases added: two per team member (P) or at least four (P+).

## Self-assessment: Way of working

Current state according to the Essence standard: ...

Was the self-assessment unanimous? Any doubts about certain items?

How have you improved so far?

Where is potential for improvement?

## Overall experience

What are your main take-aways from this project? What did you learn?

Is there something special you want to mention here?
