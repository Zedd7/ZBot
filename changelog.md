# Changelog

The changelog are a the summary of changes brought to ZBot by each version released. They don't include technical
changes that are already described in commit messages, but rather focus on functional improvements and bug fixes.

Each changelog must be formatted as follows in order to be correctly matched:
```md
## a.b.c - yyyy-mm-dd - Optional short description
- Change 1.
- Change 2.
- ...
```
where `a.b.c` is the version string.

## 1.6.4 - 2020-07-25 - Changelogs were thought to be mythical creatures before this version.
- Added the command `changelog` to display the changes brought by a specific version.
- Added the option `--all` to the command `version` to display all existing versions.
- Made the command `version` display a one-line summary of the changes brought by the displayed version(s).
- Made the command `help` show only the helper of the command that is exactly matched if it exists.
- Fixed the command `help` printing an error for missing permissions when other matching commands don't require such permissions.
- Fixed the command `help` sorting outputs by the name of the subcommand rather than by the full command path if the nest level was > 1.
- Fixed anniversaries not being celebrated at 9 am when the bot didn't restart between midnight and 9 am, and didn't celebrate the anniversaries at 9 am the day before.

## 1.6.3 - 2020-07-15 - The command `help` became slightly smarter.
- Made group commands display their helper text if invoked without subcommand.
- Made the `help` command display the bot's mention as command prefix if invoked without the custom prefix.

## 1.6.2 - 2020-07-15 - Hourly messages in a graph.
- Added the command `graph messages` to plot the number of messages from the last hour over time.

## 1.6.1 - 2020-07-11 - Total number of members in a graph.
- Added the command `graph` and its subcommand `members` to plot the total number of members over time.
- Made the group commands helper similar to the regular commands helper, with briefs and aliases.
- Allowed anniversaries celebration to run up to 1 day after intended run time.
- Changed the automessages frequency to 4 hours.
- Fixed commands `check recruitment` and `report recruitment` treating announces posted before the last registration date of a deleted announce as illegal.
- Fixed command `lottery cancel` crash.

## 1.6.0 - 2020-06-27 - How many members per role ?
- Added the command `members` to display the number of members per role.

## 1.5.5 - 2020-06-21 - Edit existing automessages.
- Added the command `automessage edit` and its subcommands `automessage edit channel` and `automessage edit message` to edit existing automessages.
- Added the option `--raw` to the command `automessage print` to print the automessage content in raw text format.
- Made the automessages loop abort if running above defined frequency.
- Reworked permission and channel checks.

## 1.5.4 - 2020-06-20 - This is an automessage. This is another automessage.
- Added the command `automessage` and its subcommands `automessage add`, `automessage list`, `automessage print` and `automessage delete` to manage automessages.
- Added the optional argument `time` to the `clear recruitment` command to only effectively clear the logs as of that time.
- Made it possible to set the option `--number` of the command `switch` to `0`.
- Made the command `help` output results in alphabetical order.
- Stopped creating the anniversaries celebration job if it already ran the same day.

## 1.5.3 - 2020-05-14 - WIP stands for Work In Progress.
- Added the command `work` and its subcommands `work start`, `work done` and `work status` to manage the work in progress status of the bot.
- Added the command `clear` and its subcommand `clear recruitment` to allow resetting the tracking of recruitment announces for a player.

## 1.5.2 - 2020-05-11 - Please talk about this elsewhere.
- Added the command `switch` to move a discussion to another channel.
- Made the command `help` filter out commands and groups marked as hidden for non-mod members.

## 1.5.1 - 2020-04-24 - The command `help` ~~is~~ has\* now a new legend.
- Added a legend for string arguments to the command `help`.
- Added a check to verify that the command is allowed in the current channel.
- Made the WoT account anniversary job repeat with a delay of one day.
- Added a link to the source message to confirmation of the commands `poll cancel`  and `lottery cancel`.

## 1.5.0 - 2020-04-21 - Happy anniversawot !
- Added a WoT account anniversary celebration feature.
- Made fetching of tank tiers an async delayed startup task to optimize the command `stats`.
- Added the time elapsed for computation in footer of the command `stats`.
- Fixed the command `stats` not working for players with 0 battle.

## 1.4.3 - 2020-04-11 - Simulate me like one of your french messages.
- Moved the lottery simulation feature of the command `lottery pick` to a new command `lottery simulate`.
- Removed the ability of the command `lottery pick` to override existing lottery parameters.
- Moved the poll simulation feature of the command `poll assess` to a new command `poll simulate`.
- Removed the ability of the command `poll assess` to override existing poll parameters.
- Fixed the embed of the command `poll assess` linking the wrong message.

## 1.4.2 - 2020-03-29 - Let's pretend this was a poll all along.
- Added the command `poll assess` to allow manual closing of running polls and to count the votes on any message that is not a poll.
- Allowed users to use the command `lottery pick` in evaluation mode without mod rights.
- Added the argument `--nest` to the command `help` to only unfold the specified number of levels of command groups.

## 1.4.1 - 2020-03-29 - I totally did not fail my poll
- Added the group command `poll edit` and its subcommands `poll edit announce`, `poll edit description`, `poll edit emojis`, `poll edit organizer` and `poll edit time` to edit ongoing polls.
- Made an error being shown when a time argument is wrongly formatted.

## 1.4.0 - 2020-03-24 - How creates the best polls: me, me or me ? Vote !
- Added the command `poll` to manage polls.
- Added the command `poll start` to start a time based poll.
- Added the command `poll list` to list currently running polls.
- Added the command `poll cancel` to cancel a currently running poll.
- Fixed commands crashing without warning when a string argument is malformed.

## 1.3.7 - 2020-03-20 - Hey, that's illegal !
- Added the command `report recrut` to delete an illegal recruitment announces and send a report to both the author and the moderator in DM.
- Made the `help` command print the help dialog for all commands or groups for which the call sequence provided with `help` matches the end of those commands or groups.

## 1.3.6 - 2020-03-20 - One command to rule them all.
- Added the command `check all` to trigger all checks at once.
- Moved all sub-commands of the command group `admin` one level up and removed the command group `admin`.
- Made the command `help` accept as argument commands that are not homonyms of their category.

## 1.3.5 - 2020-03-20 - No more spamming recruitment announces.
- Made `admin check recruitment` check that no announce is re-posted before a given timespan.

## 1.3.4 - 2020-02-29 - Break the recruitment rules and the bot will handcuff you !
- Added the command `admin check recruitment` to check the conformity of recruitment announces.

## 1.3.3 - 2020-01-01 - Edition of ongoing lotteries is the future.
- Added the group command `lottery edit` to edit ongoing lotteries.
- Added the subcommand `lottery edit announce` to edit the announce of ongoing lotteries.
- Added the subcommand `lottery edit emoji` to edit the emoji of ongoing lotteries.
- Added the subcommand `lottery edit organizer` to edit the organizer of ongoing lotteries.
- Added the subcommand `lottery edit time` to edit the run time of ongoing lotteries.
- Added the subcommand `lottery edit winners` to edit the number of winners of ongoing lotteries.
- Made the command `lottery cancel` update the embed of the lottery message.
- Added a feedback to the command `lottery setup`.
- Added a feedback to the command `lottery pick`.
- Fixed the command `lottery cancel` not working if the lottery message was deleted.
- Fixed group commands not including parent command in error message when a subcommand was missing.

## 1.3.2 - 2019-12-23 - Be your own (impatient) lottery winner (without price).
- Reworked the command `lottery pick` to allow manual execution of planned lotteries.
- Added the number of winners to the embed of planned lotteries.
- Fixed logging of non-ASCII player names.
- Fixed misfired lotteries attempting to run before that the bot is fully logged in.
- Fixed misfired lotteries attempting to unregister after execution while they were not registered.

## 1.3.1 - 2019-12-23 - Hi, I'm RoboCop on steroids.
- Made the command `admin check everyone` check that all members have at least one role.
- Made the command `admin check joueur` check that a verified nickname is used by only one player.
- Grouped the command `admin check` outputs in blocks to fasten printout.
- Fixed incorrect matching of player names for the command `admin check joueur`.

## 1.3.0 - 2019-12-15 - Hi, I'm RoboCop.
- Added the command `admin check everyone` to check that no member uses an unauthorized clan tag.
- Added the command `admin check joueur` to check that all members with the role 'Joueur' have a matching account name on WoT.
- Added the command `admin check contact` to check that all clan contacts still meet the requirements for the role.

## 1.2.0 - 2019-12-15 - "Let there be light".
- Added the command `help` to display the list of commands and their descriptions.
- Added the command `version` to display the version of the bot.
- Added the command `source` to display the link to the bot's GitHub repository.
- Added an activity status to show the command `help`.
- Fixed command usage not showing for commands called with aliases.
- Renamed the command `config` in `admin`.

## 1.1.7 - 2019-12-15 - What does this big red button do ?
- Added the command `lottery list`.
- Added the command `lottery cancel`.
- Fixed stats commands not printing the wrongly typed name of players in the error message.

## 1.1.6 - 2019-12-15 - Memento, but the part in reverse.
- Added a logger to record events to file and console.

## 1.1.5 - 2019-12-15 - You can now click pigeons, because reasons.
- Added support for server emojis in commands.
- Added the option `--no-announce` to the command `lottery setup`.
- Made an error being displayed when a non-emoji string was used in lottery commands.
- Made list of lottery players being logged.

## 1.1.4 - 2019-12-15 - If only I could remember what I need to don't forget.
- Fixed lottery jobs not correctly loading after restart.

## 1.1.3 - 2019-12-15 - Clans in da place.
- Added the command `clan` to display informations about a WoT clan.

## 1.1.2 - 2019-12-15 - Profiles in da place.
- Added the command `profile` to display the profile of a WoT player.
- Fixed the command `stats` failing when a tank id was not available in WG API.

## 1.1.1 - 2019-04-30 - Maths > Clans.
- Added the average XP and average tier to the command `stats`.
- Removed clan tag, position and emblem from the command `stats`.

## 1.1.0 - 2019-04-29 - Stats in da place.
- Added the command `stats` to display the statistics and clan-related short info of a player.
- Fixed command usage only being displayed for the first subcommand of a command group.

## 1.0.8 - 2019-04-21 - Dura lex, sed lex.
- Added a reaction listener to warn lottery players if they attempt to play without the required role.
- Allowed custom emojis to be used with lottery commands.
- Added the display of the lottery organizer in the embed of the pending message.
- Made a reaction being added when the lottery starts and removed when it finishes.
- Added the optional argument `seed` to the command `lottery pick`.

## 1.0.7 - 2019-04-21 - If Skynet emerges.
- Added the command `config logout`.

## 1.0.6 - 2019-04-07 - That's not magic, but not very far.
- Made planned lottery draws being save to database and rescheduled automagically in case of bot shutdown.
- Made winners's mention logged to file instead of their id.
- Fixed command usage not being sent for main commands.
- Added full hierarchy of subcommands to command usages.

## 1.0.5 - 2019-03-31 - Lotteries can now see into the future.
- Added the command `lottery setup` to announce lottery and schedule future winners picking.
- Added a check to test if lottery winner accepts DMs and report it to the organizer if not.
- Fixed display of dates not adjusting to the community timezone.

## 1.0.4 - 2019-03-18 - Hello, I'm a Nigerian prince. Congratulations, you just won 1 million dollars !
- Made the organizer and winners being DM to announce the result and give instructions.

## 1.0.3 - 2019-03-18 - You can resume on spamming +1 at each other.
- Made unknown commands being silently ignored.
- Added the optional argument `organizer` to the command `lottery pick`.
- Added a check on the minimum size of integer arguments.
- Added a color to lottery embeds.

## 1.0.2 - 2019-03-10 - Folders are a nice thing after all.
- Packed the command `pick` in the group command `lottery`.
- Made the result of the command `pick` display in an embed.
- Added checks on the user role for the command `lottery pick`.

## 1.0.1 - 2019-03-08 - I'm not a cheater, I'm a magician.
- Made the seed of the command `pick` being generated and printed.
- Made messages being removed if they contain a valid command `pick`.

## 1.0.0 - 2019-02-24 - Initial release
- Added the command `pick` to design winners from a set of reactions.
