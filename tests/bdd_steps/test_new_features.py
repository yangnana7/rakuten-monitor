from pytest_bdd import scenarios

# Step definitions are imported in conftest.py for global registration

# Load all the feature files
scenarios("../../features/01_new_product.feature")
scenarios("../../features/02_restock.feature")
scenarios("../../features/03_no_change.feature")
scenarios("../../features/04_unreachable.feature")
