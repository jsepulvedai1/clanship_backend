from django.test import TestCase
from users.models import SystemSetting
from core.schema import schema

class SubscriptionVersionBlockingTestCase(TestCase):
    def setUp(self):
        self.setting = SystemSetting.get_settings()

    def test_version_blocking_logic(self):
        self.setting.subscriptions_enabled_ios = True
        self.setting.subscriptions_min_version_ios = "1.0.5"
        self.setting.subscriptions_blocked_versions_ios = "1.0.6, 1.0.7"
        self.setting.save()

        # Older than min_version
        self.assertFalse(self.setting.is_subscription_enabled_for_version('ios', '1.0.4'))
        # Equal to min_version
        self.assertTrue(self.setting.is_subscription_enabled_for_version('ios', '1.0.5'))
        self.assertTrue(self.setting.is_subscription_enabled_for_version('ios', '1.0.5+10'))
        # Blocked version
        self.assertFalse(self.setting.is_subscription_enabled_for_version('ios', '1.0.6'))
        self.assertFalse(self.setting.is_subscription_enabled_for_version('ios', '1.0.6+99'))
        self.assertFalse(self.setting.is_subscription_enabled_for_version('ios', '1.0.7'))
        # Newer allowed version
        self.assertTrue(self.setting.is_subscription_enabled_for_version('ios', '1.0.8'))

    def test_master_switch_disabled(self):
        self.setting.subscriptions_enabled_ios = False
        self.setting.save()
        self.assertFalse(self.setting.is_subscription_enabled_for_version('ios', '1.0.8'))

    def test_graphql_app_config_query(self):
        self.setting.subscriptions_enabled_ios = True
        self.setting.subscriptions_min_version_ios = "1.0.5"
        self.setting.subscriptions_blocked_versions_ios = "1.0.6"
        self.setting.save()

        q_blocked = '''
        query {
          appConfig(platform: "ios", appVersion: "1.0.6") {
            subscriptionsEnabledIos
            isSubscriptionsEnabled
            subscriptionsBlockedVersionsIos
            subscriptionsMinVersionIos
          }
        }
        '''
        res_blocked = schema.execute(q_blocked)
        self.assertFalse(res_blocked.data['appConfig']['subscriptionsEnabledIos'])
        self.assertFalse(res_blocked.data['appConfig']['isSubscriptionsEnabled'])
        self.assertEqual(res_blocked.data['appConfig']['subscriptionsBlockedVersionsIos'], "1.0.6")

        q_allowed = '''
        query {
          appConfig(platform: "ios", appVersion: "1.0.8") {
            subscriptionsEnabledIos
            isSubscriptionsEnabled
          }
        }
        '''
        res_allowed = schema.execute(q_allowed)
        self.assertTrue(res_allowed.data['appConfig']['subscriptionsEnabledIos'])
        self.assertTrue(res_allowed.data['appConfig']['isSubscriptionsEnabled'])
