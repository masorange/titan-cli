# When To Create Operation

Create an operation when a step contains logic that is:

1. not UI
2. not context access
3. more than trivial
4. likely reusable or easier to test separately

Examples:

1. parsing input into structured values
2. validating domain constraints
3. combining multiple client calls
4. filtering and ranking returned data
