Issue #0: `slugify("Hello,  World!")` returns `"hello--world"` but should return `"hello-world"`.

Fix the bug. Repeated separators should collapse into a single hyphen.
