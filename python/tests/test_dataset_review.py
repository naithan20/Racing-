import pytest

from racingedge_data.dataset_review import (
    DatasetReviewInput,
    create_dataset_review,
    get_dataset_review,
    list_dataset_reviews,
)


class TestCreateDatasetReview:
    def test_creates_and_reads_back(self, tmp_db_conn):
        review_id = create_dataset_review(
            tmp_db_conn,
            DatasetReviewInput(
                dataset_name="Fixture UK/IRE Historical Results",
                source="Kaggle: fixture-uk-ireland-horse-racing-results",
                licence_stated="CC0: Public Domain",
                licence_url="https://example.invalid/licence",
                original_provider="Fixture Racing Data Co",
                redistribution_permitted=True,
                research_use_permitted=True,
                commercial_use_permitted=False,
                provenance_confidence="COMMUNITY_UNVERIFIED",
                reviewer_notes="Uploader claims CC0 but does not cite the original data provider's own terms.",
            ),
        )
        tmp_db_conn.commit()

        review = get_dataset_review(tmp_db_conn, review_id)
        assert review is not None
        assert review["datasetName"] == "Fixture UK/IRE Historical Results"
        assert review["provenanceConfidence"] == "COMMUNITY_UNVERIFIED"
        assert review["redistributionPermitted"] == 1
        assert review["commercialUsePermitted"] == 0

    def test_null_permission_fields_mean_not_established(self, tmp_db_conn):
        review_id = create_dataset_review(
            tmp_db_conn,
            DatasetReviewInput(dataset_name="Fixture Dataset", source="fixture-source"),
        )
        tmp_db_conn.commit()
        review = get_dataset_review(tmp_db_conn, review_id)
        assert review["redistributionPermitted"] is None
        assert review["researchUsePermitted"] is None
        assert review["commercialUsePermitted"] is None
        assert review["provenanceConfidence"] == "UNKNOWN"

    def test_rejects_invalid_provenance_confidence(self, tmp_db_conn):
        with pytest.raises(ValueError):
            create_dataset_review(
                tmp_db_conn,
                DatasetReviewInput(
                    dataset_name="Fixture Dataset", source="fixture-source", provenance_confidence="NOT_A_REAL_STATUS"
                ),
            )


class TestListDatasetReviews:
    def test_lists_most_recent_first(self, tmp_db_conn):
        first_id = create_dataset_review(
            tmp_db_conn, DatasetReviewInput(dataset_name="Fixture Dataset A", source="fixture-a")
        )
        tmp_db_conn.commit()
        second_id = create_dataset_review(
            tmp_db_conn, DatasetReviewInput(dataset_name="Fixture Dataset B", source="fixture-b")
        )
        tmp_db_conn.commit()

        reviews = list_dataset_reviews(tmp_db_conn)
        ids = [r["id"] for r in reviews]
        assert ids.index(second_id) < ids.index(first_id)
