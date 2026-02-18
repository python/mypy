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



### `is_overlapping_types@mypy/meet.py`
Lizard's output for `is_overlapping_types` in `mypy/meet.py` is as follows:
```
  NLOC    CCN   token  PARAM  length  location
------------------------------------------------
    168     81     1185      6      322  is_overlapping_types@336-657@./mypy/meet.py
```

With counting each logical clause (e.g., `and`, `or`) as well as the `for` and `if` statements inside of comprehensions, we arrive at a CC of **80**, being off by one compared to lizard output. The difference of 1 compared to Lizard’s result is likely due to how the tool counts certain Python-specific constructs, it might count the generator expression for example.

The purpose of is_overlapping_types() is to check whether two mypy types overlap at runtime, meaning whether it is possible for any value to be both left and right. It is used for reachability checks and for verifying whether overload variants or unions might match. Since it must handle many different type categories and each category requires its own branching rules and return paths, it is in my opinion, justified that this function has a high cyclomatic complexity, but some of this logic I think should be moved out into helper function to improve readability.

There are no exceptions or try/catch blocks. The function contains a few asserts for paths that should never occur as sanity checks, but in general it attempts to explicitly handle every case and return early instead of relying on a generic try/catch.

There is quiet a bit of documentation around the different branches.


The quality of our own coverage measurement is quiet limited as it's very annoying to add new paths and requires quiet a bit of boilerplate. This function has no ternary operators or excpetions so that is not applicable here. I did not use an automated tool for this one.

The result of the coverage analyzer was that 49/51 branches were already covered under existing test suite. Of these 3, 2 were unreachable by design so impossible to test. So I added the one test for the branch I could reach and created 3 different tests for path coverage. This was also very difficult to look at the existing test suite and try to figure out if the path had already been covered so I did my best to try and figure it out, but it's almost impossible to actually check on such a large test suite.

### `comparing_type_narrowing_help@mypy/checker.py`
Lizard's output for `covering_type_narrowing_helper` in `mypy/checker.py` is as follows:

```
  NLOC    CCN   token  PARAM  length  location
------------------------------------------------
    126     30     618      2      171  comparison_type_narrowing_helper@6452-6622@mypy/checker.py
```

By manually counting the number of decision points (if, elif, logical and/or, and loop constructs) I obtained 29 decision points, resulting in a cyclomatic complexity of 30, which matches Lizard’s output.

Initially, some logical operators inside compound conditions were easy to overlook, but after including each logical clause as a decision point, the manual count aligned with the tool. Therefore, the results are consistent and clear.

This function is both complex and fairly long. With an NLOC of 126 and total length of 171 lines, it is noticeably larger than what is typically considered simple or easy to maintain. The nested conditional structure contributes significantly to the high cyclomatic complexity.

The purpose of comparison_type_narrowing_helper() is to support mypy’s type checker by analyzing comparison expressions (such as x == y, x is y, membership checks, and chained comparisons) and determining how variable types can be narrowed based on the comparison outcome. It returns type maps describing the narrowed types for different execution branches. Because Python comparisons and type relationships are rich and varied, the function must handle many special cases, which largely explains the high complexity.

There are no try/except blocks in this function, so exception handling is not taken into account in the cyclomatic complexity measurement. 

The documentation of the function gives a overview of its purpose. However, given the large number of branches and special cases, the documentation does not fully describe all possible outcomes. Understanding the exact behavior in edge cases requires reading the implementation. Additional comments would help.

The result of the coverage analysis for comparison_type_narrowing_helper() showed that most branches (13/14) were already exercised by the existing mypy test suite. However, Branch 2 was determined to be unreachable by design, making it impossible to cover through additional tests. I then chose to think about path coverage. To improve coverage, I therefore added two additional tests focused on path coverage, ensuring that different combinations of comparison and membership logic are exercised. Identifying whether particular paths were already covered was challenging due to the size and complexity of the existing test suite.



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
