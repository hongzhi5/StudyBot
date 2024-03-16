
class Utils:
    @staticmethod
    def convert_seconds_to_time(total_study_time):
        days, remainder = divmod(total_study_time, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        time_str = ""
        if days > 0:
            time_str += f'{int(days)} D, '
        if hours > 0:
            time_str += f'{int(hours)} H, '
        time_str += f'{int(minutes)} m'

        return time_str


