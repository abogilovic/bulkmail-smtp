import keep_alive
import os
import dkim
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from email.utils import make_msgid
import time
import re
import random

keep_alive.keep_alive()
dkim_pk = os.environ['DKIM_PK']
dkim_sel = os.environ['DKIM_SEL']
dkim_domain = os.environ['DKIM_DOMAIN']
banned_send_domains = ["yahoo.com", "ymail.com", "aol.com", "yahoo.co.uk", "gmx.de", "aim.com", "gmx.net", "rocketmail.com", "web.de"]
approved_send_domains = ["gmail.com", "hotmail.com", "outlook.com", "protonmail.com", "srv1.mail-tester.com"]
test = os.environ['TEST'] == '1'
port = int(os.environ['PORT'])
smtp = os.environ['SMTP']
api_key_validate_mail = os.environ['API_VALID_MAIL']
email_list_txt = 'testlist.txt' if test else os.environ['LIST_NAME']
progress_save = 'list_index.txt'
sent_amount = 'mail_sent_amount.txt'
html_template_path = 'index.html'
smtp_failure = 'smtp_failure_count.txt'
sender_address = os.environ['SENDER_ADDR']
sender_pass = os.environ['SENDER_PASS']
sender_name = os.environ['SENDER_NAME']
mails_per_day = 1090
mails_per_hour = int(mails_per_day/24)
mail_wait_list = []
seconds_in_hour = 60*60 #seconds
seconds_window_hourly_mailsend = 40*60 #seconds
per_mail_gap = 20 #seconds
synonyms = [['*I am*',['I am', "I'm"]],
                ['*giving*',['sending', 'giving', 'gifting', 'delivering']],
                ['*1PI*',['1PI', '1 Pi', '1 PI', '1Pi', '1π', '1 π', '1π']],
                ['*a unique*',['a unique', 'an interesting', 'a promising']],
                ['*digital currency*',['digital currency', 'cryptocurrency', 'digital coin']],
                ['*currently*',['currently', 'right now', 'at this moment']],
                ['*testnet*',['testnet', 'testing']],
                ['*sold*',['sold', 'exchanged', 'traded']],
                ['*utilities*',['utilities', 'apps', 'web apps', 'utilities']],
                ['*developed*',['developed', 'created', 'developed', 'engineered']],
                ['*claim*',['redeem', 'claim']],
                ['*mining*',['mining', 'minting', 'earning']],
                ['*app*',['app', 'application']],
                ['*20+ millions*',['20+ millions', '20M+']],
                ['*investment*',['activity', 'opportunity', 'contribution', 'chance', 'suggestion', 'entrance', 'commitment', 'engagement', 'process']]
                        ]


if not test: time.sleep(0)


mail_template_content = '''Pi Network is *a unique* *digital currency* with an ecosystem *currently* in a *testnet* phase. (*id*)
*I am* *giving* *1PI* coin to *username* which you can then *claim* it by downloading an *app* from your official *app* store, and then continue with the PI *mining*.

INVITATION CODE: gillabo'''
email_regex = re.compile(r"[^@]+@[^@]+\.[^@]+")
with open(html_template_path, 'r') as f:
  html_mail_template_content = f.read()

actual_seconds_window_hourly_mailsend = 0
mails_sent_this_hour = 0
beginning_sleep = 0

count = 0
previous_invalid_mail = False

with open(progress_save, 'r') as f: jump = int(f.read())
with open(sent_amount, 'r') as f: sent_emails = int(f.read())
with open(smtp_failure, 'r') as f: smtp_fail_count = int(f.read())

def unique_content_gen(html, plain, username):
        imgs = ['pi1.jpg', 'pi2.jpg', 'pi3.jpg', 'pi4.png', 'pi5.jpeg', 'pi6.png', 'pi7.jpg']
        html = html.replace('pi1.jpg', imgs.pop(random.randint(0, len(imgs)-1)), 1)
        html = html.replace('pi2.jpg', imgs.pop(random.randint(0, len(imgs)-1)), 1)
        for v in synonyms: html = html.replace(v[0], v[1][random.randint(0, len(v[1])-1)])
        for v in synonyms: plain = plain.replace(v[0], v[1][random.randint(0, len(v[1])-1)])
        html = html.replace('*username*', username)
        plain = plain.replace('*username*', username)
        
        idn = ''.join(random.choice('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ') for x in range(6))

        rv = random.random()
        if rv < 0.33:
                subject = '{0} have received *1PI* coin. {1}'                                               #You abogilovic1 have received 1PI Coin. J3H7S0
                for v in synonyms: subject = subject.replace(v[0], v[1][random.randint(0, len(v[1])-1)])
                subject = subject.format(username.capitalize(), idn)
        elif rv < 0.66:
                subject = 'You have received *1PI* *digital currency*! {0}'                                           #Receive 1PI digital currency! J3H7S0
                for v in synonyms: subject = subject.replace(v[0], v[1][random.randint(0, len(v[1])-1)])
                subject = subject.format(idn)
        else:
                subject = '{0} can *claim* *1PI* *digital currency* | {1}'                                      #Abogilovic1 can claim 1PI digital currency | J3H7S0
                for v in synonyms: subject = subject.replace(v[0], v[1][random.randint(0, len(v[1])-1)])
                subject = subject.format(username.capitalize(), idn)
                
        return [plain.replace('*id*', idn), html.replace('*id*', idn), idn, subject]

    

with open(email_list_txt) as f:
        for index, line in enumerate(f):
                if index < jump: continue

                if mails_sent_this_hour == 0 and not previous_invalid_mail:
                        mail_wait_list.clear()
                        mail_wait_list = [random.uniform(seconds_window_hourly_mailsend/mails_per_hour - per_mail_gap, seconds_window_hourly_mailsend/mails_per_hour + per_mail_gap) for i in range(mails_per_hour)]
                        actual_seconds_window_hourly_mailsend = sum(mail_wait_list)
                        beginning_sleep = random.uniform(0, (seconds_in_hour - actual_seconds_window_hourly_mailsend) if index!=jump else 0)
                        end_sleep = seconds_in_hour - beginning_sleep - actual_seconds_window_hourly_mailsend
                        print("Hourly session starts!")
                        print("Waits: [BEG, WIND, END] -> " + "[%.2f" % beginning_sleep + ", %.2f" % actual_seconds_window_hourly_mailsend +", %.2f" % end_sleep + "] [s]")
                        print("Hourly start session wait: " + "%.2f" % beginning_sleep + " [s]")
                        time.sleep(beginning_sleep)
                
                raw_address = line.strip().split(':')[0]
                receiver_address = raw_address.lower()
                count += 1
                try:
                        if email_regex.match(receiver_address) == None or not(receiver_address.split('@')[1] in approved_send_domains) or not requests.get('https://verify.gmass.co/verify?email={0}&key={1}'.format(receiver_address, api_key_validate_mail)).json()['Valid']:
                                print(receiver_address + ' is not valid for delivering!')
                                previous_invalid_mail = True
                                continue
                except:
                        print('Mail verification error.')
                        previous_invalid_mail = True
                        continue

                previous_invalid_mail = False            
                
                unique_content = unique_content_gen(html_mail_template_content, mail_template_content, raw_address.split('@')[0])
                message = MIMEMultipart('alternative')
                send_name_addr = formataddr((str(Header(sender_name, 'utf-8')), sender_address))
                message['From'] = send_name_addr
                message['Reply-to'] = send_name_addr
                message['To'] = receiver_address
                message['Subject'] = unique_content[3]
                message['Message-ID'] = make_msgid()
                #message['Sender'] = sender_name
                message.add_header('List-Unsubscribe', '<mailto:head+{0}@joinpicoin.com?subject=unsubscribe>'.format(unique_content[2]))
                
                message.attach(MIMEText(unique_content[0], 'plain'))
                message.attach(MIMEText(unique_content[1], 'html'))

                headers=[b'from', b'reply-to', b'to', b'subject', b'message-id', b'list-unsubscribe']
                signature = dkim.sign(message.as_bytes(), bytes(dkim_sel, 'utf-8'), bytes(dkim_domain, 'utf-8'), dkim_pk.encode(), include_headers=headers).decode()
                message['DKIM-Signature'] = signature[len("DKIM-Signature: "):]

                try:
                        if not test: print("Next mail sends in: " + "%.2f" % mail_wait_list[mails_sent_this_hour] + " [s]")
                        time.sleep(10) if test else time.sleep(mail_wait_list[mails_sent_this_hour])
                        mails_sent_this_hour += 1
                        sent_emails += 1

                        connected = False
                        session = smtplib.SMTP(smtp, port)
                        session.login(sender_address, sender_pass)
                        connected = True
                        session.sendmail(sender_address, receiver_address, message.as_string())
                        print("Email ", sent_emails, " successfully sent to ", receiver_address)
                        session.quit()
                except:
                        try:
                                if connected:
                                        session.quit()
                                        connected = False

                                print("Reconnecting... (lost connection)")
                                time.sleep(15)
                                session = smtplib.SMTP(smtp, port)
                                session.login(sender_address, sender_pass)
                                connected = True
                                session.sendmail(sender_address, receiver_address, message.as_string())
                                print("Email ", jump + count, " successfully sent to ", receiver_address)
                                session.quit()
                        except:
                                print("Can't login to smtp or send email. (lost connection)")
                                if connected: session.quit()
                                print("Wait " + str(10*60) + " [s]")
                                sent_emails -= 1
                                smtp_fail_count += 1
                                with open(smtp_failure, 'w') as f: f.write(str(smtp_fail_count))
                                time.sleep(10*60)
                
                with open(sent_amount, 'w') as f: f.write(str(sent_emails))
                with open(progress_save, 'w') as f: f.write(str(jump + count))

                if mails_sent_this_hour >= mails_per_hour:
                        mails_sent_this_hour = 0
                        print("Hourly session ends!")
                        print("Hourly end session wait: " + "%.2f" % end_sleep + " [s]")
                        time.sleep(end_sleep)