from ethereum import utils


def test_slash_no_dbl_prepare(casper, funded_privkey, deposit_amount,
                              induct_validator, mk_vote, fake_hash, casper_chain):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.total_curdyn_deposits_scaled() == deposit_amount

    vote_1 = mk_vote(
        validator_index,
        casper.recommended_target_hash(),
        casper.current_epoch(),
        casper.recommended_source_epoch(),
        funded_privkey
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        casper.current_epoch(),
        casper.recommended_source_epoch(),
        funded_privkey
    )

    next_dynasty = casper.dynasty() + 1
    assert casper.dynasty_wei_delta(casper.dynasty() + 1) == 0

    casper.slash(vote_1, vote_2)

    assert casper.total_slashed(casper.current_epoch()) == deposit_amount
    assert casper.dynasty_wei_delta(next_dynasty) == \
        (-deposit_amount / casper.deposit_scale_factor())
    assert casper.validators__is_slashed(validator_index)
    assert casper.validators__end_dynasty(validator_index) == next_dynasty
    assert casper.validators__total_deposits_at_logout(validator_index) == deposit_amount


def test_slash_no_surround(casper, funded_privkey, deposit_amount, new_epoch,
                           induct_validator, mk_vote, fake_hash, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    assert casper.total_curdyn_deposits_scaled() == deposit_amount

    vote_1 = mk_vote(
        validator_index,
        casper.recommended_target_hash(),
        casper.current_epoch(),
        casper.recommended_source_epoch() - 1,
        funded_privkey
    )
    vote_2 = mk_vote(
        validator_index,
        fake_hash,
        casper.current_epoch() - 1,
        casper.recommended_source_epoch(),
        funded_privkey
    )

    next_dynasty = casper.dynasty() + 1
    assert casper.dynasty_wei_delta(casper.dynasty() + 1) == 0

    casper.slash(vote_1, vote_2)

    assert casper.total_slashed(casper.current_epoch()) == deposit_amount
    assert casper.dynasty_wei_delta(next_dynasty) == \
        (-deposit_amount / casper.deposit_scale_factor())
    assert casper.validators__is_slashed(validator_index)
    assert casper.validators__end_dynasty(validator_index) == next_dynasty
    assert casper.validators__total_deposits_at_logout(validator_index) == deposit_amount


def test_slash_after_logout_delay(casper, funded_privkey, deposit_amount,
                                  induct_validator, mk_suggested_vote, mk_slash_votes,
                                  new_epoch, logout_validator):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    scaled_deposit_size = casper.validators__deposit(validator_index)

    assert casper.total_curdyn_deposits_scaled() == deposit_amount

    logout_validator(validator_index, funded_privkey)
    end_dynasty = casper.validators__end_dynasty(validator_index)
    assert casper.validators__total_deposits_at_logout(validator_index) == deposit_amount

    assert casper.dynasty_wei_delta(end_dynasty) == -scaled_deposit_size

    # step past validator's end_dynasty
    dynasty_logout_delay = casper.DYNASTY_LOGOUT_DELAY()
    for _ in range(dynasty_logout_delay + 1):
        casper.vote(mk_suggested_vote(validator_index, funded_privkey))
        new_epoch()

    new_deposit_size = casper.deposit_size(validator_index)
    new_scaled_deposit_size = casper.validators__deposit(validator_index)
    # should have a bit more from rewards
    assert new_scaled_deposit_size > scaled_deposit_size

    end_dynasty = casper.validators__end_dynasty(validator_index)
    assert casper.dynasty() == end_dynasty + 1
    assert casper.dynasty_wei_delta(casper.dynasty() + 1) == 0

    vote_1, vote_2 = mk_slash_votes(validator_index, funded_privkey)
    casper.slash(vote_1, vote_2)

    assert casper.total_slashed(casper.current_epoch()) == new_deposit_size
    assert casper.validators__is_slashed(validator_index)
    assert casper.validators__end_dynasty(validator_index) == end_dynasty
    # unchanged
    assert casper.validators__total_deposits_at_logout(validator_index) == deposit_amount

    # validator already out of current deposits. should not change dynasty_wei_delta
    assert casper.dynasty_wei_delta(end_dynasty) == -new_scaled_deposit_size
    assert casper.dynasty_wei_delta(casper.dynasty() + 1) == 0


def test_slash_after_logout_before_logout_delay(casper, funded_privkey, deposit_amount,
                                                induct_validator,
                                                mk_suggested_vote, mk_slash_votes,
                                                new_epoch, logout_validator):
    validator_index = induct_validator(funded_privkey, deposit_amount)
    scaled_deposit_size = casper.validators__deposit(validator_index)

    assert casper.total_curdyn_deposits_scaled() == deposit_amount

    logout_validator(validator_index, funded_privkey)
    end_dynasty = casper.validators__end_dynasty(validator_index)

    assert casper.dynasty_wei_delta(end_dynasty) == -scaled_deposit_size

    # step forward but not up to end_dynasty
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    new_epoch()

    new_deposit_size = casper.deposit_size(validator_index)
    new_scaled_deposit_size = casper.validators__deposit(validator_index)

    assert casper.dynasty() < end_dynasty - 1
    assert casper.dynasty_wei_delta(casper.dynasty() + 1) == 0
    assert casper.dynasty_wei_delta(end_dynasty) == -new_scaled_deposit_size

    vote_1, vote_2 = mk_slash_votes(validator_index, funded_privkey)
    casper.slash(vote_1, vote_2)

    assert casper.total_slashed(casper.current_epoch()) == new_deposit_size
    assert casper.validators__is_slashed(validator_index)
    assert casper.validators__end_dynasty(validator_index) == casper.dynasty() + 1

    # remove deposit from next dynasty rather than end_dynasty
    assert casper.dynasty_wei_delta(end_dynasty) == 0
    assert casper.dynasty_wei_delta(casper.dynasty() + 1) == -new_scaled_deposit_size
    # unchanged
    assert casper.validators__total_deposits_at_logout(validator_index) == deposit_amount


def test_total_slashed(casper, funded_privkey, deposit_amount, new_epoch,
                       induct_validator, mk_suggested_vote, mk_slash_votes):
    validator_index = induct_validator(funded_privkey, deposit_amount)

    vote_1, vote_2 = mk_slash_votes(validator_index, funded_privkey)
    casper.slash(vote_1, vote_2)

    current_epoch = casper.current_epoch()
    assert casper.total_slashed(current_epoch) == deposit_amount
    assert casper.total_slashed(current_epoch + 1) == 0

    # step forwrd
    casper.vote(mk_suggested_vote(validator_index, funded_privkey))
    new_epoch()

    current_epoch = casper.current_epoch()
    assert casper.total_slashed(current_epoch - 1) == deposit_amount
    assert casper.total_slashed(current_epoch) == deposit_amount


def test_double_slash_fails(casper, funded_privkey, deposit_amount,
                            induct_validator, mk_slash_votes, assert_tx_failed):
    validator_index = induct_validator(funded_privkey, deposit_amount)

    vote_1, vote_2 = mk_slash_votes(validator_index, funded_privkey)
    casper.slash(vote_1, vote_2)
    assert_tx_failed(lambda: casper.slash(vote_1, vote_2))


def test_withdraw_after_slash(casper, casper_chain,
                              funded_privkeys, deposit_amount, new_epoch,
                              induct_validators, mk_suggested_vote, mk_slash_votes):
    validator_indexes = induct_validators(funded_privkeys, [deposit_amount] * len(funded_privkeys))
    slashed_fraction_of_total_deposits = 1.0 / len(funded_privkeys)

    # 0th gets slashed
    slashed_index = validator_indexes[0]
    slashed_privkey = funded_privkeys[0]
    slashed_public_key = utils.privtoaddr(slashed_privkey)
    # the rest remain
    logged_in_indexes = validator_indexes[1:]
    logged_in_privkeys = funded_privkeys[1:]

    vote_1, vote_2 = mk_slash_votes(slashed_index, slashed_privkey)
    casper.slash(vote_1, vote_2)

    current_epoch = casper.current_epoch()
    assert casper.total_slashed(current_epoch) == deposit_amount
    assert casper.total_slashed(current_epoch + 1) == 0

    # slashed validator can withdraw after end_dynasty plus delay
    for i in range(casper.WITHDRAWAL_DELAY() + 2):
        for i, validator_index in enumerate(logged_in_indexes):
            casper.vote(mk_suggested_vote(validator_index, logged_in_privkeys[i]))
        new_epoch()

    prev_balance = casper_chain.head_state.get_balance(slashed_public_key)
    casper.withdraw(slashed_index)
    balance = casper_chain.head_state.get_balance(slashed_public_key)
    assert balance > prev_balance

    expected_slashed_fraction = slashed_fraction_of_total_deposits * 3
    expected_withdrawal_fraction = 1 - expected_slashed_fraction
    expected_withdrawal_amount = expected_withdrawal_fraction * deposit_amount
    withdrawal_amount = balance - prev_balance
    assert withdrawal_amount < deposit_amount
    # should be less than because of some loss due to inactivity during withdrawal period
    assert withdrawal_amount < expected_withdrawal_amount
    # ensure within proximity to expected_withdrawal_amount
    assert withdrawal_amount > expected_withdrawal_amount * 0.9
