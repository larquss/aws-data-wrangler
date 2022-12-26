"""Amazon QuickSight Module."""

from awswrangler.quicksight._cancel import cancel_ingestion  # noqa
from awswrangler.quicksight._create import create_athena_data_source, create_athena_dataset, create_ingestion  # noqa
from awswrangler.quicksight._delete import (  # noqa
    delete_all_dashboards,
    delete_all_data_sources,
    delete_all_datasets,
    delete_all_templates,
    delete_dashboard,
    delete_data_source,
    delete_dataset,
    delete_template,
)
from awswrangler.quicksight._describe import (  # noqa
    describe_dashboard,
    describe_data_source,
    describe_data_source_permissions,
    describe_dataset,
    describe_ingestion,
)
from awswrangler.quicksight._get_list import (  # noqa
    get_dashboard_id,
    get_dashboard_ids,
    get_data_source_arn,
    get_data_source_arns,
    get_data_source_id,
    get_data_source_ids,
    get_dataset_id,
    get_dataset_ids,
    get_template_id,
    get_template_ids,
    list_dashboards,
    list_data_sources,
    list_datasets,
    list_group_memberships,
    list_groups,
    list_iam_policy_assignments,
    list_iam_policy_assignments_for_user,
    list_ingestions,
    list_templates,
    list_users,
)
