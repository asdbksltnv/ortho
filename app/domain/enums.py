from enum import StrEnum


class Role(StrEnum):
    DOCTOR = "doctor"
    NURSE = "nurse"
    ANAESTHESIOLOGIST = "anaesthesiologist"
    HEAD_OF_DEPARTMENT = "head_of_department"
    HEAD_NURSE = "head_nurse"
    ADMIN = "admin"


class CaseStatus(StrEnum):
    ADMITTED = "admitted"
    IN_PREPARATION = "in_preparation"
    APPROVED_FOR_SURGERY = "approved_for_surgery"
    CALLED_TO_OR = "called_to_or"
    LEFT_WARD = "left_ward"
    IN_OR = "in_or"
    RETURNED_TO_WARD = "returned_to_ward"
    TRANSFERRED_ICU = "transferred_icu"
    POST_OP = "post_op"
    DISCHARGED = "discharged"


class ItemStatus(StrEnum):
    NOT_STARTED = "not_started"
    PENDING = "pending"
    DONE = "done"
    PROBLEM = "problem"
    NOT_APPLICABLE = "not_applicable"


class Blocking(StrEnum):
    ALWAYS = "always"
    PER_PROCEDURE = "per_procedure"
    IF_APPLICABLE = "if_applicable"
    DAY_OF_SURGERY = "day_of_surgery"


class ConsentType(StrEnum):
    SURGICAL = "surgical"
    ANAESTHESIA = "anaesthesia"


class AuditAction(StrEnum):
    VIEW = "view"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    COPY = "copy"
    EXPORT = "export"
    LOGIN = "login"
