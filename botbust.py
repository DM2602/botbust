import praw
import os
import re
from collections import deque

#set globals

r=praw.Reddit(user_agent='mod helper by captainmeta4',
              username = 'botbust',
              password = os.environ.get('password'),
              client_id= os.environ.get('client_id'),
              client_secret= os.environ.get('client_secret')
              )

ME = r.user.me()
SUBREDDIT = r.subreddit('BotBust')
LOG_SUB = r.subreddit('BotBustLog')
LOG_TITLE = "/u/{0} banned from /r/{1}"

BAN_NOTE = "BotBusted!"
BAN_MESSAGE = ("Known comment bots are not welcome in /r/{0}"
               "\n\n*[I am a bot, and this action was performed automatically](/r/botbust/about/sticky). "
               "If you wish to dispute your status as a blacklisted comment bot, please "
               "[click here](https://www.reddit.com/message/compose?to=%2Fr%2FBotBust&subject=ban%20dispute:%20{1}).*"
                )
WELCOME_MESSAGE = ("Hello, moderators of /r/{0}"
                   "\n\nI am now helping keep your subreddit free of known worthless comment bots."
                   "\n\nFor more information, or to submit a worthless bot to my banlist, please visit /r/BotBust."
                   )
NSFW_MESSAGE = ("Hello, moderators of /r/{0}"
                "\n\nThank you for your interest in BotBust."
                "\n\nHowever, BotBust is not available for NSFW subreddits. Thank you for understanding.")

class Bot():

    def __init__(self):

        self.moderated=[]
        self.friends=[]
        self.triggered=deque([],maxlen=100)

    def reload_moderated(self):

        self.moderated=[]

        for subreddit in r.user.moderator_subreddits(limit=None):
            self.moderated.append(subreddit.display_name)

    def reload_friends(self):
        self.friends=[]
        for user in r.user.friends():
            self.friends.append(user.name)


    def run(self):

        #Not currently checking for mod invites due to unannounced inbox change
        
        self.check_for_mod_invites()
        self.reload_moderated()
        self.reload_friends()

        while True:
            self.check_for_new_banned()
            self.patrol_r_friends()
            self.check_for_mod_invites()

    def check_for_mod_invites(self):

        

        for message in r.inbox.unread(limit=None):
            message.mark_read()

            #filter out everything but PMs
            if not message.fullname.startswith('t4_'):
                continue

            #filter out everything not sent by a subreddit
            if message.author is not None:
                continue

            #filter out messages not associated with a subreddit
            if message.subreddit is None:
                continue
            
            try:
                if not message.subreddit.over18:
                    message.subreddit.mod.accept_invite()
                    print('accepted invite to /r/'+message.subreddit.display_name)
                    self.moderated.append(message.subreddit.display_name)
                    self.log_add(message.subreddit.display_name)
                else:
                    message.reply(NSFW_MESSAGE.format(message.subreddit.display_name))
                    
            except:
                pass
        

    def patrol_r_friends(self):
        
        #load comments
        
        for comment in r.subreddit('friends').comments(limit=100):

            #All comments here will be by a banned account.
            #the only thing to check is that it's in a moderated subreddit

            if comment.subreddit.display_name not in self.moderated:
                continue

            if comment.banned_by:
                continue

            #ignore comments whose authors are botbustproof
            if comment.author_flair_css_class:
                if "botbustproof" in comment.author_flair_css_class:
                    continue
                    
            #avoid duplicate work
            if comment.id in self.triggered:
                continue

            

            #at this point the ban needs to be issued
            
            # protect against insufficient mod perms by using try
            try:
                comment.mod.remove()
            except:
                pass

            print('banning /u/'+comment.author.name+' from /r/'+comment.subreddit.display_name)
            try:
                comment.subreddit.banned.add(comment.author, note="BotBusted!", ban_message = BAN_MESSAGE.format(comment.subreddit.display_name, comment.author.name))
                self.log_ban(comment)
            except:
                pass
              
            #avoid duplicate work
            self.triggered.append(comment.id)
                      
    def log_add(self, name):
        url="https://reddit.com/r/{}".format(name)
        title="Accepted mod invite to /r/{}".format(name)
        LOG_SUB.submit(title, url=url).mod.approve()
                      
                      
        

    def log_ban(self, comment):

        user = comment.author.name
        sub = comment.subreddit.display_name
        url = "https://reddit.com{}".format(comment.permalink())
        
        title = LOG_TITLE.format(user, sub)

        LOG_SUB.submit(title, url=url).mod.approve()
        
    def check_for_new_banned(self):


        
        need_to_reload=False

        #process pending check-for-bans. search by flair
        for submission in SUBREDDIT.search("flair_css_class:checkban",syntax="lucene",limit=None):

            #ignore any stray search results
            if submission.link_flair_css_class !="checkban":
                continue

            #get the username
            name = re.match("https?://(\w{1,3}\.)?reddit.com/u(ser)?/([A-Za-z0-9_-]+)/?", submission.url).group(3)

            print('checking ban state on /u/'+name)
            
            if name in self.friends:
                submission.mod.flair(text="Already Banned!", css_class="banned")

            else:
                submission.mod.flair(text="For Review", css_class = "exclam")
            
            

        #process pending bans. search by flair
        for submission in SUBREDDIT.search("flair_css_class:banpending",syntax="lucene",limit=None):

            #ignore any stray search results
            if submission.link_flair_css_class != "banpending":
                continue

            need_to_reload = True

            #get the username
            name = re.match("https?://(\w{1,3}\.)?reddit.com/u(ser)?/([A-Za-z0-9_-]+)/?", submission.url).group(3)

            #friend the redditor
            r.redditor(name).friend()
            print(name+" banned!")
            submission.mod.flair(text="Banned!", css_class="banned")


            #process pending unbans

        for submission in SUBREDDIT.search("flair_css_class:unbanpending",syntax="lucene", limit=None):
            
            if submission.link_flair_css_class != "unbanpending":
                continue

            need_to_reload = True

            #get the username
            name = re.match("https?://(\w{1,3}\.)?reddit.com/u(ser)?/([A-Za-z0-9_-]+)/?", submission.url).group(3)

            #unfriend the redditor
            r.redditor(name).unfriend()
            print(name+" unbanned")
            submission.mod.flair(text="Unbanned", css_class="unbanned")

        

        if need_to_reload:
            self.reload_friends()


if __name__=="__main__":
    b=Bot()
    b.run()
