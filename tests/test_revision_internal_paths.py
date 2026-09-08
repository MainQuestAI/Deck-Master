from workflow import actions
import pytest

@pytest.mark.parametrize('relative',['build/revisions','build'])
def test_snapshot_and_pointer_storage_cannot_follow_outside_symlink(tmp_path,relative):
    root=tmp_path/'run';root.mkdir()
    outside=tmp_path/'outside';outside.mkdir()
    link=root/relative;link.parent.mkdir(exist_ok=True);link.symlink_to(outside,target_is_directory=True)
    env=actions.create_action_envelope(action_id='commit',task_id='t',scope_pages=['P001'],input_fingerprint='fp')
    with pytest.raises(actions.ActionEnvelopeError,match='escapes'):
        actions.stage_action_result(root,env,{'svg':'new'})
        actions.commit_action_result(root,env,current_input_fingerprint='fp',targets={'svg':root/'high_density_build/svg/P001.svg'})
    assert list(outside.iterdir())==[]
