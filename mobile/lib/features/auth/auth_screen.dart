import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_controller.dart';
import '../daily/daily_screen.dart';
import '../reports/reports_screen.dart';

class AuthScreen extends ConsumerStatefulWidget {
  const AuthScreen({super.key});

  @override
  ConsumerState<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends ConsumerState<AuthScreen> {
  final _form = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _timezone = TextEditingController(text: 'Africa/Cairo');
  bool _register = false;
  DateTime? _start;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _timezone.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_form.currentState!.validate()) return;
    final password = _password.text;
    _password.clear();
    await ref
        .read(authControllerProvider.notifier)
        .authenticate(
          email: _email.text,
          password: password,
          register: _register,
          timezone: _timezone.text,
          trackingStartDate: _start?.toIso8601String().split('T').first,
        );
    if (mounted && ref.read(authControllerProvider).account != null) {
      _email.clear();
      setState(() => _register = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(authControllerProvider);
    final controller = ref.read(authControllerProvider.notifier);
    final account = state.account;
    return Scaffold(
      appBar: AppBar(title: const Text('محاسبة')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (state.error != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 16),
                      child: Text(
                        state.error!,
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ),
                  if (state.restoreFailed) ...[
                    const Text('بيانات الدخول المحفوظة لم تُمسح.'),
                    const SizedBox(height: 16),
                    FilledButton(
                      onPressed: state.busy ? null : controller.restore,
                      child: const Text('إعادة المحاولة'),
                    ),
                  ] else if (account != null) ...[
                    Text(
                      'مرحبًا بك في محاسبة',
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 16),
                    Text(account.email, textDirection: TextDirection.ltr),
                    Text('المنطقة الزمنية: ${account.timezone}'),
                    if (!account.emailVerified)
                      const Text('البريد لم يتم تأكيده بعد.'),
                    const SizedBox(height: 24),
                    FilledButton(
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => DailyScreen(account: account),
                        ),
                      ),
                      child: const Text('المحاسبة اليوم'),
                    ),
                    OutlinedButton(
                      onPressed: () => Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => ReportsScreen(account: account),
                        ),
                      ),
                      child: const Text('التقارير'),
                    ),
                    FilledButton(
                      onPressed: state.busy ? null : controller.logout,
                      child: const Text('تسجيل الخروج'),
                    ),
                  ] else if (!state.busy)
                    Form(
                      key: _form,
                      child: AutofillGroup(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            Text(
                              _register ? 'إنشاء حساب' : 'تسجيل الدخول',
                              style: Theme.of(context).textTheme.headlineSmall,
                            ),
                            const SizedBox(height: 24),
                            TextFormField(
                              controller: _email,
                              key: const Key('email'),
                              textDirection: TextDirection.ltr,
                              keyboardType: TextInputType.emailAddress,
                              autofillHints: const [AutofillHints.email],
                              autocorrect: false,
                              decoration: const InputDecoration(
                                labelText: 'البريد الإلكتروني',
                              ),
                              validator: (value) =>
                                  value != null && value.trim().contains('@')
                                  ? null
                                  : 'أدخل بريدًا إلكترونيًا صحيحًا',
                            ),
                            const SizedBox(height: 16),
                            TextFormField(
                              controller: _password,
                              key: const Key('password'),
                              obscureText: true,
                              enableSuggestions: false,
                              autocorrect: false,
                              maxLength: 128,
                              autofillHints: [
                                _register
                                    ? AutofillHints.newPassword
                                    : AutofillHints.password,
                              ],
                              decoration: InputDecoration(
                                labelText: 'كلمة المرور',
                                helperText: _register
                                    ? '12 حرفًا على الأقل'
                                    : null,
                              ),
                              validator: (value) =>
                                  value == null ||
                                      value.length < (_register ? 12 : 1)
                                  ? (_register
                                        ? 'استخدم 12 حرفًا على الأقل'
                                        : 'أدخل كلمة المرور')
                                  : null,
                            ),
                            if (_register) ...[
                              const SizedBox(height: 16),
                              TextFormField(
                                controller: _timezone,
                                key: const Key('timezone'),
                                textDirection: TextDirection.ltr,
                                decoration: const InputDecoration(
                                  labelText: 'المنطقة الزمنية',
                                ),
                                validator: (value) =>
                                    value == null || value.trim().isEmpty
                                    ? 'أدخل المنطقة الزمنية'
                                    : null,
                              ),
                              TextButton(
                                onPressed: () async {
                                  final selected = await showDatePicker(
                                    context: context,
                                    initialDate: _start ?? DateTime.now(),
                                    firstDate: DateTime(1900),
                                    lastDate: DateTime.now().add(
                                      const Duration(days: 1),
                                    ),
                                  );
                                  if (selected != null && mounted) {
                                    setState(() => _start = selected);
                                  }
                                },
                                child: Text(
                                  _start == null
                                      ? 'بداية المتابعة: اليوم (تغيير)'
                                      : 'بداية المتابعة: ${_start!.toIso8601String().split('T').first}',
                                ),
                              ),
                            ],
                            const SizedBox(height: 24),
                            FilledButton(
                              onPressed: _submit,
                              key: const Key('submit'),
                              child: Text(_register ? 'إنشاء الحساب' : 'دخول'),
                            ),
                            TextButton(
                              onPressed: () => setState(() {
                                _register = !_register;
                                _password.clear();
                              }),
                              child: Text(
                                _register
                                    ? 'لديك حساب؟ تسجيل الدخول'
                                    : 'مستخدم جديد؟ إنشاء حساب',
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  if (state.busy)
                    const Padding(
                      padding: EdgeInsets.all(24),
                      child: CircularProgressIndicator(),
                    ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
