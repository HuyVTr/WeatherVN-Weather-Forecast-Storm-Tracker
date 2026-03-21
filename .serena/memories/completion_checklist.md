# Completion Checklist

When a task is completed, ensure the following:

1.  **Functionality**: Verify that the new feature or fix works as expected.
2.  **Testing**:
    - Run existing tests if applicable: `python tests/test_ml_accuracy.py --all`.
    - Create new test cases in `tests/` if new functionality was added.
3.  **Style**: Ensure code follows `snake_case` for Python and includes descriptive docstrings (Vietnamese or English as appropriate).
4.  **Documentation**: Update `README.md` if there are changes to setup, configuration, or usage.
5.  **Database**: If models were changed, ensure migration or update scripts are provided or executed.
6.  **Static Assets**: If frontend changes were made, verify responsiveness and cross-browser compatibility.
