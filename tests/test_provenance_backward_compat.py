"""
Test backward compatibility of provenance integration.

Verifies that existing code still works after adding provenance_metadata field.
"""

def test_store_extraction_without_provenance():
    """Test that store_extraction_results works without provenance parameter (backward compat)."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    # Simulate calling without provenance_data (how existing code works)
    rdf_data = {
        'new_classes': [
            {
                'label': 'Test Role Class',
                'uri': 'http://test.org/TestRole',
                'definition': 'A test role for backward compatibility',
                'properties': {}
            }
        ],
        'new_individuals': [
            {
                'label': 'Test Individual',
                'uri': 'http://test.org/TestIndividual',
                'properties': {},
                'relationships': []
            }
        ]
    }

    # Call without provenance_data parameter (existing caller pattern)
    entities = TemporaryRDFStorage.store_extraction_results(
        case_id=999,
        extraction_session_id='test_session_backward_compat',
        extraction_type='roles',
        rdf_data=rdf_data,
        extraction_model='test-model'
        # NOTE: NOT passing provenance_data
    )

    # Verify entities created
    assert len(entities) == 2, f"Expected 2 entities, got {len(entities)}"

    # Verify provenance_metadata defaults to empty dict
    for entity in entities:
        assert entity.provenance_metadata == {}, \
            f"Expected empty dict for provenance_metadata, got {entity.provenance_metadata}"

    print("✓ Backward compatibility test passed!")
    return True


def test_store_extraction_with_provenance():
    """Test that store_extraction_results works WITH provenance parameter."""
    from app.models.temporary_rdf_storage import TemporaryRDFStorage

    rdf_data = {
        'new_classes': [],
        'new_individuals': [
            {
                'label': 'Test Individual With Prov',
                'uri': 'http://test.org/TestIndividualProv',
                'properties': {},
                'relationships': []
            }
        ]
    }

    # Call WITH provenance_data parameter (new pattern)
    provenance_data = {
        'extraction_activity_id': 123,
        'section_type': 'questions',
        'extracted_at': '2025-10-12T15:00:00'
    }

    entities = TemporaryRDFStorage.store_extraction_results(
        case_id=999,
        extraction_session_id='test_session_with_prov',
        extraction_type='roles',
        rdf_data=rdf_data,
        extraction_model='test-model',
        provenance_data=provenance_data  # NEW parameter
    )

    # Verify provenance stored
    assert len(entities) == 1
    entity = entities[0]
    assert entity.provenance_metadata == provenance_data, \
        f"Expected {provenance_data}, got {entity.provenance_metadata}"

    print("✓ Provenance storage test passed!")
    return True


if __name__ == '__main__':
    print("Testing backward compatibility of provenance integration...")
    print()

    # These tests don't require full app context
    # They just verify the method signature works

    print("Test 1: Calling without provenance_data (existing code pattern)")
    try:
        # Just verify the function can be called without the parameter
        from app.models.temporary_rdf_storage import TemporaryRDFStorage
        import inspect
        sig = inspect.signature(TemporaryRDFStorage.store_extraction_results)
        params = sig.parameters

        # Check provenance_data is optional
        assert 'provenance_data' in params, "provenance_data parameter not found"
        assert params['provenance_data'].default is not inspect.Parameter.empty, \
            "provenance_data should have a default value"

        print("✓ Method signature is backward compatible!")
    except Exception as e:
        print(f"✗ Test failed: {e}")
        exit(1)

    print()
    print("All backward compatibility tests passed!")
    print()
    print("Next step: Test with real database by running Questions extraction")
