alter table tasks_announcement_localization add constraint composite_tann_local_uc_key unique(announcement_id, member_id,partner_id,role_id);
alter table tasks_recurring_info_update_localization add constraint composite_trcurr_local_uc_key unique(recurring_info_update_id, member_id,partner_id,role_id);
