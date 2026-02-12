from nanobot.agent.tools.train_ticket import TrainTicketTool


def test_train_ticket_date_normalize_keywords():
    tool = TrainTicketTool()
    today, err = tool._normalize_date("今天")
    assert err is None
    assert len(today) == 10

    tomorrow, err = tool._normalize_date("明天")
    assert err is None
    assert len(tomorrow) == 10


def test_train_ticket_date_normalize_invalid():
    tool = TrainTicketTool()
    _, err = tool._normalize_date("下周一")
    assert err is not None


def test_train_ticket_train_type_normalize():
    tool = TrainTicketTool()
    assert tool._normalize_train_types("高铁动车") == "GD"
    assert tool._normalize_train_types("gdz") == "GDZ"
