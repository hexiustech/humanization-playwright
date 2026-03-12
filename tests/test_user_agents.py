import pytest
from humanization import user_agents
from humanization.user_agents import DEFAULT_USER_AGENTS


@pytest.fixture(autouse=True)
def reset_pool():
    """Reset the pool before and after each test."""
    user_agents.reset()
    yield
    user_agents.reset()


def test_get_random_returns_string():
    ua = user_agents.get_random()
    assert isinstance(ua, str)
    assert ua in user_agents.list_agents()


def test_get_random_empty_raises():
    user_agents.clear()
    with pytest.raises(ValueError, match="pool is empty"):
        user_agents.get_random()


def test_list_agents_returns_copy():
    agents = user_agents.list_agents()
    assert agents == list(DEFAULT_USER_AGENTS)
    agents.append("should not affect pool")
    assert len(user_agents.list_agents()) == len(DEFAULT_USER_AGENTS)


def test_add():
    user_agents.clear()
    user_agents.add("CustomUA/1.0")
    assert user_agents.list_agents() == ["CustomUA/1.0"]


def test_add_duplicate_skipped():
    initial_count = len(user_agents.list_agents())
    user_agents.add(DEFAULT_USER_AGENTS[0])
    assert len(user_agents.list_agents()) == initial_count


def test_remove():
    user_agents.clear()
    user_agents.add("CustomUA/1.0")
    user_agents.remove("CustomUA/1.0")
    assert user_agents.list_agents() == []


def test_remove_nonexistent_raises():
    user_agents.clear()
    with pytest.raises(ValueError, match="not found"):
        user_agents.remove("nonexistent")


def test_clear():
    user_agents.clear()
    assert user_agents.list_agents() == []


def test_reset():
    user_agents.clear()
    user_agents.reset()
    assert user_agents.list_agents() == list(DEFAULT_USER_AGENTS)


def test_save_and_load(tmp_path):
    filepath = str(tmp_path / "ua.json")
    user_agents.clear()
    user_agents.add("TestUA/1.0")
    user_agents.add("TestUA/2.0")
    user_agents.save(filepath)

    user_agents.clear()
    assert user_agents.list_agents() == []

    user_agents.load(filepath)
    assert user_agents.list_agents() == ["TestUA/1.0", "TestUA/2.0"]


def test_load_nonexistent_raises():
    with pytest.raises(FileNotFoundError):
        user_agents.load("/nonexistent/path/ua.json")
